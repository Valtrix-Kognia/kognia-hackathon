import json
import logging
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("kognia.latency")

_USER_KEYS = (
    "transcription_delay",
    "end_of_turn_delay",
    "on_user_turn_completed_delay",
)
_AGENT_KEYS = (
    "llm_node_ttft",
    "llm_node_ttfs",
    "tts_node_ttfb",
    "playback_latency",
    "e2e_latency",
)
MAX_COMPLETED = 200

Publish = Callable[[str, dict[str, Any]], None]


@dataclass
class ToolTiming:
    tool: str
    duration_ms: float
    cache_hit: bool
    http_ms: float = 0.0
    start_ms: float | None = None
    end_ms: float | None = None


@dataclass
class TurnLatency:
    """Timeline of one conversational turn.

    marks_ms are milliseconds relative to the moment the user turn was committed, measured
    with time.perf_counter() inside the worker process. Wall-clock timestamps reported by
    LiveKit in the same process are converted with the wall/perf pair captured at commit.
    """

    turn_id: str
    decision: str
    t0_perf: float
    t0_wall: float
    marks_ms: dict[str, float] = field(default_factory=dict)
    stages_ms: dict[str, float] = field(default_factory=dict)
    tools: list[ToolTiming] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    client: dict[str, Any] = field(default_factory=dict)
    outcome: str = "open"

    @property
    def first_audio_ms(self) -> float | None:
        start = self.marks_ms.get("playout_started")
        stop = self.marks_ms.get("user_stopped")
        if start is None or stop is None:
            return None
        return round(start - stop, 1)

    def to_payload(self) -> dict[str, Any]:
        stages = dict(self.stages_ms)
        if self.first_audio_ms is not None:
            stages["first_audio"] = self.first_audio_ms
        return {
            "turn_id": self.turn_id,
            "decision": self.decision,
            "outcome": self.outcome,
            "marks_ms": self.marks_ms,
            "stages_ms": stages,
            "tools": [t.__dict__ for t in self.tools],
            "socrata_ms": round(
                sum(t.duration_ms for t in self.tools if not t.cache_hit), 1
            ),
            "socrata_http_ms": round(sum(t.http_ms for t in self.tools), 1),
            "events": self.events,
            "client": self.client,
        }


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    low, high = int(rank), min(int(rank) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


class LatencyMetricsService:
    """Per-turn tracer correlating LiveKit metrics, pipeline marks, tools and playback."""

    def __init__(
        self,
        publish: Publish | None = None,
        perf_clock: Callable[[], float] = time.perf_counter,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._publish = publish or (lambda _t, _p: None)
        self._perf = perf_clock
        self._wall = wall_clock
        self._current: TurnLatency | None = None
        self._completed: list[TurnLatency] = []
        self._by_id: dict[str, TurnLatency] = {}
        self._counters: dict[str, int] = {}

    @property
    def current_turn_id(self) -> str | None:
        return self._current.turn_id if self._current else None

    def start_turn(self, turn_id: str, decision: str) -> None:
        if self._current is not None:
            self._close(self._current, "sin_respuesta_completa")
        self._counters = {}
        turn = TurnLatency(turn_id, decision, self._perf(), self._wall())
        self._current = turn
        self._by_id[turn_id] = turn
        if len(self._by_id) > MAX_COMPLETED:
            self._by_id.pop(next(iter(self._by_id)))

    def mark(self, name: str, numbered: bool = False) -> None:
        turn = self._current
        if turn is None:
            return
        if numbered:
            self._counters[name] = self._counters.get(name, 0) + 1
            name = f"{name}_{self._counters[name]}"
        turn.marks_ms.setdefault(name, round((self._perf() - turn.t0_perf) * 1000, 1))

    def mark_wall(self, name: str, wall_time: float) -> None:
        turn = self._current
        if turn is not None:
            turn.marks_ms.setdefault(name, round((wall_time - turn.t0_wall) * 1000, 1))

    def event(self, name: str, **data: Any) -> None:
        turn = self._current
        if turn is not None:
            at_ms = round((self._perf() - turn.t0_perf) * 1000, 1)
            turn.events.append({"name": name, "at_ms": at_ms, **data})

    def annotate(self, turn_id: str | None, name: str, **data: Any) -> None:
        """Attach an event to a turn even after it closed (e.g. a late interruption)."""
        turn = self._by_id.get(turn_id) if turn_id else None
        if turn is None:
            return
        at_ms = round((self._perf() - turn.t0_perf) * 1000, 1)
        turn.events.append({"name": name, "at_ms": at_ms, **data})
        logger.info(
            "turn event %s %s",
            turn_id,
            json.dumps({"name": name, "at_ms": at_ms, **data}),
        )

    def relative_ms(self) -> float | None:
        turn = self._current
        return round((self._perf() - turn.t0_perf) * 1000, 1) if turn else None

    def on_user_message(self, metrics: dict[str, Any]) -> None:
        turn = self._current
        if turn is None:
            return
        self._copy(turn, metrics, _USER_KEYS)
        stopped = metrics.get("stopped_speaking_at")
        if isinstance(stopped, int | float):
            self.mark_wall("user_stopped", stopped)

    def on_tool(self, timing: ToolTiming) -> None:
        if self._current is not None:
            self._current.tools.append(timing)

    def on_agent_speaking(self, wall_time: float) -> None:
        self.mark_wall("playout_started", wall_time)

    def on_agent_message(self, metrics: dict[str, Any]) -> dict[str, Any] | None:
        turn = self._current
        if turn is None or "llm_node_ttft" not in metrics:
            return None
        self._copy(turn, metrics, _AGENT_KEYS)
        return self._close(turn, "respondido")

    def close_without_llm(self, outcome: str) -> None:
        if self._current is not None:
            self._close(self._current, outcome)

    def on_client_metrics(self, turn_id: str, data: dict[str, Any]) -> None:
        turn = self._by_id.get(turn_id)
        if turn is None:
            logger.info(
                "client latency for unknown turn %s: %s", turn_id, json.dumps(data)
            )
            return
        turn.client.update(data)
        logger.info("client latency %s", json.dumps({"turn_id": turn_id, **data}))
        self._publish(
            "metrics.client", {"turn_id": turn_id, **data, "summary": self.summary()}
        )

    def summary(self) -> dict[str, Any]:
        answered = [t for t in self._completed if t.outcome == "respondido"]
        e2e = [
            t.stages_ms["e2e_latency"] for t in answered if "e2e_latency" in t.stages_ms
        ]
        ttft = [
            t.stages_ms["llm_node_ttft"]
            for t in answered
            if "llm_node_ttft" in t.stages_ms
        ]
        first_audio = [
            t.first_audio_ms for t in self._completed if t.first_audio_ms is not None
        ]
        browser = [
            t.client["decision_to_audible_ms"]
            for t in self._completed
            if isinstance(t.client.get("decision_to_audible_ms"), int | float)
        ]
        return {
            "turns": len(answered),
            "first_audio_p50_ms": _round(percentile(first_audio, 50)),
            "first_audio_p95_ms": _round(percentile(first_audio, 95)),
            "e2e_p50_ms": _round(percentile(e2e, 50)),
            "e2e_p95_ms": _round(percentile(e2e, 95)),
            "e2e_mean_ms": _round(statistics.fmean(e2e)) if e2e else None,
            "llm_ttft_p50_ms": _round(percentile(ttft, 50)),
            "browser_audible_p50_ms": _round(percentile(browser, 50)),
            "browser_audible_p95_ms": _round(percentile(browser, 95)),
        }

    def _close(self, turn: TurnLatency, outcome: str) -> dict[str, Any]:
        turn.outcome = outcome
        if self._current is turn:
            self._current = None
        self._completed.append(turn)
        del self._completed[:-MAX_COMPLETED]
        payload = {**turn.to_payload(), "summary": self.summary()}
        logger.info("turn latency %s", json.dumps(payload))
        self._publish("metrics.turn", payload)
        return payload

    @staticmethod
    def _copy(
        turn: TurnLatency, metrics: dict[str, Any], keys: tuple[str, ...]
    ) -> None:
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, int | float):
                turn.stages_ms[key] = round(value * 1000, 1)


def _round(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None
