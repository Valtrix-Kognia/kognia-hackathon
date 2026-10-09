import asyncio
import time
from dataclasses import dataclass, field

from app.application.services.text_matching import best_matches, normalize
from app.domain.errors import UnknownFilterValueError
from app.domain.models.dataset_columns import Column
from app.infrastructure.socrata.socrata_client import MAX_PAGE_SIZE, SocrataClient
from app.infrastructure.socrata.soql import Projection, SoqlQuery

NIVEL_SIN_DATO = "sin_dato"

_NIVEL_WORDS = {
    "1": "1",
    "UNO": "1",
    "I": "1",
    "PRIMER": "1",
    "PRIMERO": "1",
    "PRIMER NIVEL": "1",
    "2": "2",
    "DOS": "2",
    "II": "2",
    "SEGUNDO": "2",
    "SEGUNDO NIVEL": "2",
    "3": "3",
    "TRES": "3",
    "III": "3",
    "TERCER": "3",
    "TERCERO": "3",
    "TERCER NIVEL": "3",
    "SIN DATO": NIVEL_SIN_DATO,
    "SIN NIVEL": NIVEL_SIN_DATO,
    "NO INFORMADO": NIVEL_SIN_DATO,
}


@dataclass
class CatalogSnapshot:
    places: dict[str, list[str]] = field(default_factory=dict)
    naturalezas: list[str] = field(default_factory=list)
    niveles: dict[str, int] = field(default_factory=dict)
    grupos: list[str] = field(default_factory=list)
    fecha_corte: str | None = None
    total_rows: int = 0
    loaded_at: float = 0.0

    @property
    def nivel_missing_ratio(self) -> float:
        missing = self.niveles.get(NIVEL_SIN_DATO, 0)
        return missing / self.total_rows if self.total_rows else 0.0


class ValueCatalog:
    """Canonical categorical values loaded from the official API, used as a value whitelist."""

    def __init__(self, client: SocrataClient, ttl_s: int) -> None:
        self._client = client
        self._ttl_s = ttl_s
        self._snapshot: CatalogSnapshot | None = None
        self._lock = asyncio.Lock()

    async def snapshot(self) -> CatalogSnapshot:
        if self._snapshot and time.monotonic() - self._snapshot.loaded_at < self._ttl_s:
            return self._snapshot
        async with self._lock:
            if (
                self._snapshot
                and time.monotonic() - self._snapshot.loaded_at < self._ttl_s
            ):
                return self._snapshot
            self._snapshot = await self._load()
            return self._snapshot

    async def _load(self) -> CatalogSnapshot:
        places_q = SoqlQuery(
            projections=[Column.DEPARTAMENTO, Column.MUNICIPIO],
            group_by=[Column.DEPARTAMENTO, Column.MUNICIPIO],
        )
        (
            places_rows,
            nat_rows,
            nivel_rows,
            grupo_rows,
            corte_rows,
        ) = await asyncio.gather(
            self._client.query(places_q.render(), page_size=MAX_PAGE_SIZE),
            self._client.query(self._values_query(Column.NATURALEZA)),
            self._client.query(self._values_query(Column.NIVEL_ATENCION)),
            self._client.query(self._values_query(Column.GRUPO_CAPACIDAD)),
            self._client.query(self._values_query(Column.FECHA_CORTE)),
        )
        snapshot = CatalogSnapshot(loaded_at=time.monotonic())
        for row in places_rows:
            dep, mun = row.get(Column.DEPARTAMENTO), row.get(Column.MUNICIPIO)
            if dep and mun:
                snapshot.places.setdefault(dep, []).append(mun)
        snapshot.naturalezas = [
            r[Column.NATURALEZA] for r in nat_rows if r.get(Column.NATURALEZA)
        ]
        snapshot.grupos = [
            r[Column.GRUPO_CAPACIDAD]
            for r in grupo_rows
            if r.get(Column.GRUPO_CAPACIDAD)
        ]
        for row in nivel_rows:
            key = row.get(Column.NIVEL_ATENCION) or NIVEL_SIN_DATO
            snapshot.niveles[key] = int(row["n"])
        snapshot.total_rows = sum(snapshot.niveles.values())
        cortes = [
            r[Column.FECHA_CORTE] for r in corte_rows if r.get(Column.FECHA_CORTE)
        ]
        snapshot.fecha_corte = "; ".join(cortes) or None
        return snapshot

    @staticmethod
    def _values_query(column: Column) -> str:
        return SoqlQuery(
            projections=[column, Projection("count(*)", "n")], group_by=[column]
        ).render()

    async def resolve_departamento(self, raw: str) -> str:
        snap = await self.snapshot()
        matches, suggestions = best_matches(raw, list(snap.places))
        if len(matches) != 1:
            raise UnknownFilterValueError("departamento", raw, suggestions or matches)
        return matches[0]

    async def resolve_municipio(
        self, raw: str, departamento: str | None
    ) -> tuple[list[str], list[str]]:
        """Return (canonical municipio names, departamentos where they were found)."""
        snap = await self.snapshot()
        scope = (
            {departamento: snap.places.get(departamento, [])}
            if departamento
            else snap.places
        )
        found_names: set[str] = set()
        found_deps: set[str] = set()
        all_suggestions: list[str] = []
        for dep, municipios in scope.items():
            matches, suggestions = best_matches(raw, municipios)
            if matches:
                found_names.update(matches)
                found_deps.add(dep)
            all_suggestions.extend(suggestions)
        if not found_names:
            raise UnknownFilterValueError(
                "municipio", raw, sorted(set(all_suggestions))[:3]
            )
        if len({normalize(n) for n in found_names}) > 1:
            raise UnknownFilterValueError("municipio", raw, sorted(found_names)[:3])
        return sorted(found_names), sorted(found_deps)

    async def resolve_naturaleza(self, raw: str) -> str:
        snap = await self.snapshot()
        stem = normalize(raw)[:4]
        matches = [
            nat
            for nat in snap.naturalezas
            if len(stem) == 4 and normalize(nat).startswith(stem)
        ]
        if len(matches) != 1:
            raise UnknownFilterValueError("naturaleza", raw, snap.naturalezas)
        return matches[0]

    async def resolve_nivel(self, raw: str) -> str:
        snap = await self.snapshot()
        key = normalize(raw).replace("NIVEL", "").strip() or normalize(raw)
        value = _NIVEL_WORDS.get(key) or _NIVEL_WORDS.get(normalize(raw))
        if value is None or (value != NIVEL_SIN_DATO and value not in snap.niveles):
            raise UnknownFilterValueError(
                "nivel_atencion",
                raw,
                sorted(k for k in snap.niveles if k != NIVEL_SIN_DATO),
            )
        return value

    async def resolve_grupo(self, raw: str) -> str:
        snap = await self.snapshot()
        norm = normalize(raw)
        for candidate in (raw, norm.rstrip("S"), norm + "S", norm + "ES"):
            matches, _ = best_matches(candidate, snap.grupos)
            if len(matches) == 1:
                return matches[0]
        raise UnknownFilterValueError("grupo_capacidad", raw, snap.grupos)
