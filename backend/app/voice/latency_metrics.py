import json
import logging
import statistics
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


@dataclass
class ToolTiming:
    tool: str
    duration_ms: float
    cache_hit: bool


@dataclass
class TurnLatency:
    turn_index: int
    user_message_id: str | None = None
    user_stopped_at: float | None = None
    stages_ms: dict[str, float] = field(default_factory=dict)
    tools: list[ToolTiming] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "user_message_id": self.user_message_id,
            "stages_ms": self.stages_ms,
            "tools": [t.__dict__ for t in self.tools],
            "socrata_ms": round(
                sum(t.duration_ms for t in self.tools if not t.cache_hit), 1
            ),
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
    """Builds a per-turn latency breakdown from LiveKit's ChatMessage.metrics and tool timings.

    All stage values come from the framework's monotonic measurements inside the worker;
    nothing is estimated here.
    """

    def __init__(self) -> None:
        self._turn_index = 0
        self._current: TurnLatency | None = None
        self._completed: list[TurnLatency] = []

    def on_user_message(self, message_id: str, metrics: dict[str, Any]) -> None:
        self._turn_index += 1
        self._current = TurnLatency(
            turn_index=self._turn_index, user_message_id=message_id
        )
        self._copy(metrics, _USER_KEYS)
        stopped = metrics.get("stopped_speaking_at")
        self._current.user_stopped_at = (
            stopped if isinstance(stopped, int | float) else None
        )

    def on_agent_speaking(self, wall_time: float) -> None:
        turn = self._current
        if (
            turn is None
            or turn.user_stopped_at is None
            or "first_audio" in turn.stages_ms
        ):
            return
        turn.stages_ms["first_audio"] = round(
            (wall_time - turn.user_stopped_at) * 1000, 1
        )

    def on_tool(self, timing: ToolTiming) -> None:
        if self._current is None:
            self._turn_index += 1
            self._current = TurnLatency(turn_index=self._turn_index)
        self._current.tools.append(timing)

    def on_agent_message(self, metrics: dict[str, Any]) -> dict[str, Any] | None:
        if self._current is None or "llm_node_ttft" not in metrics:
            return None
        self._copy(metrics, _AGENT_KEYS)
        turn, self._current = self._current, None
        if "e2e_latency" not in turn.stages_ms:
            return None
        self._completed.append(turn)
        payload = {**turn.to_payload(), "summary": self.summary()}
        logger.info("turn latency %s", json.dumps(payload))
        return payload

    def summary(self) -> dict[str, Any]:
        e2e = [t.stages_ms["e2e_latency"] for t in self._completed]
        ttft = [
            t.stages_ms["llm_node_ttft"]
            for t in self._completed
            if "llm_node_ttft" in t.stages_ms
        ]
        first_audio = [
            t.stages_ms["first_audio"]
            for t in self._completed
            if "first_audio" in t.stages_ms
        ]
        return {
            "turns": len(e2e),
            "first_audio_p50_ms": _round(percentile(first_audio, 50)),
            "first_audio_p95_ms": _round(percentile(first_audio, 95)),
            "e2e_p50_ms": _round(percentile(e2e, 50)),
            "e2e_p95_ms": _round(percentile(e2e, 95)),
            "e2e_mean_ms": _round(statistics.fmean(e2e)) if e2e else None,
            "llm_ttft_p50_ms": _round(percentile(ttft, 50)),
        }

    def _copy(self, metrics: dict[str, Any], keys: tuple[str, ...]) -> None:
        assert self._current is not None
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, int | float):
                self._current.stages_ms[key] = round(value * 1000, 1)


def _round(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None
