import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.models.dataset_columns import METRIC_EXPRESSIONS, Column, Metric
from app.infrastructure.socrata.socrata_client import MAX_PAGE_SIZE, SocrataClient
from app.infrastructure.socrata.soql import Projection, SoqlQuery

logger = logging.getLogger("kognia.aggregates")

COUNT_METRICS = (Metric.REGISTROS, Metric.PRESTADORES, Metric.SEDES)
Key = tuple[str | None, str | None]


@dataclass
class AggregateSnapshot:
    """Official counts downloaded from the API, keyed by (departamento, naturaleza)."""

    counts: dict[Key, dict[Metric, int]] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    loaded_monotonic: float = field(default_factory=time.monotonic)


class AggregateCache:
    """Preloads the most asked counts so common questions skip a Socrata round trip.

    Loading happens in the background; until it finishes (or if it fails) callers get
    None and query the API live. Values are exactly what the API returned.
    """

    def __init__(self, client: SocrataClient, ttl_s: float) -> None:
        self._client = client
        self._ttl_s = ttl_s
        self._snapshot: AggregateSnapshot | None = None
        self._task: asyncio.Task[None] | None = None

    def start_loading(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._load(), name="kognia-aggregates")

    def lookup(
        self, departamento: str | None, naturaleza: str | None
    ) -> tuple[dict[Metric, int], datetime] | None:
        snapshot = self._snapshot
        if snapshot is None:
            return None
        if time.monotonic() - snapshot.loaded_monotonic > self._ttl_s:
            self.start_loading()
            return None
        values = snapshot.counts.get((departamento, naturaleza))
        return (values, snapshot.fetched_at) if values else None

    def ranking(
        self, metric: Metric, naturaleza: str | None
    ) -> tuple[list[tuple[str, int]], datetime] | None:
        snapshot = self._snapshot
        if snapshot is None or metric not in COUNT_METRICS:
            return None
        rows = [
            (dep, values[metric])
            for (dep, nat), values in snapshot.counts.items()
            if dep is not None and nat == naturaleza
        ]
        return (rows, snapshot.fetched_at) if rows else None

    async def _load(self) -> None:
        started = time.perf_counter()
        projections = [
            Projection(METRIC_EXPRESSIONS[m], m.value) for m in COUNT_METRICS
        ]
        queries = {
            "total": SoqlQuery(projections=list(projections)),
            "naturaleza": SoqlQuery(
                projections=[Column.NATURALEZA, *projections],
                group_by=[Column.NATURALEZA],
            ),
            "departamento": SoqlQuery(
                projections=[Column.DEPARTAMENTO, *projections],
                group_by=[Column.DEPARTAMENTO],
            ),
            "departamento_naturaleza": SoqlQuery(
                projections=[Column.DEPARTAMENTO, Column.NATURALEZA, *projections],
                group_by=[Column.DEPARTAMENTO, Column.NATURALEZA],
            ),
        }
        try:
            results = await asyncio.gather(
                *(
                    self._client.query(q.render(), page_size=MAX_PAGE_SIZE)
                    for q in queries.values()
                )
            )
        except Exception:
            logger.warning(
                "aggregate preload failed; live queries will be used", exc_info=True
            )
            return
        snapshot = AggregateSnapshot()
        for rows in results:
            for row in rows:
                key = (row.get(Column.DEPARTAMENTO), row.get(Column.NATURALEZA))
                snapshot.counts[key] = {
                    m: int(float(row.get(m.value) or 0)) for m in COUNT_METRICS
                }
        self._snapshot = snapshot
        logger.info(
            "aggregates preloaded: %d keys in %.0f ms",
            len(snapshot.counts),
            (time.perf_counter() - started) * 1000,
        )
