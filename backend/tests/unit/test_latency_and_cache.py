import asyncio

import pytest

from app.infrastructure.socrata.query_cache import QueryCache
from app.voice.latency_metrics import LatencyMetricsService, ToolTiming, percentile


def test_percentile_interpolates() -> None:
    assert percentile([], 50) is None
    assert percentile([100.0], 95) == 100.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5


class Clocks:
    def __init__(self) -> None:
        self.perf = 100.0
        self.wall = 1000.0

    def advance(self, seconds: float) -> None:
        self.perf += seconds
        self.wall += seconds


def test_turn_trace_correlates_stages_tools_and_browser() -> None:
    clocks = Clocks()
    published: list[tuple[str, dict]] = []
    service = LatencyMetricsService(
        publish=lambda kind, data: published.append((kind, data)),
        perf_clock=lambda: clocks.perf,
        wall_clock=lambda: clocks.wall,
    )
    service.start_turn("t1", "respond")
    service.on_user_message({"end_of_turn_delay": 0.5, "stopped_speaking_at": 999.4})
    clocks.advance(0.2)
    service.mark("llm_start", numbered=True)
    clocks.advance(0.9)
    service.mark("llm_first_token", numbered=True)
    service.on_tool(ToolTiming("count_ips", 800.0, cache_hit=False, http_ms=650.0))
    clocks.advance(1.0)
    service.mark("llm_start", numbered=True)
    assert service.on_agent_message({}) is None
    clocks.advance(0.5)
    service.on_agent_speaking(clocks.wall)
    payload = service.on_agent_message({"e2e_latency": 3.2, "llm_node_ttft": 0.8})
    assert payload is not None
    assert payload["turn_id"] == "t1"
    assert payload["marks_ms"]["user_stopped"] == -600.0
    assert payload["marks_ms"]["llm_start_1"] == 200.0
    assert payload["marks_ms"]["llm_start_2"] == 2100.0
    assert payload["stages_ms"]["first_audio"] == 3200.0
    assert payload["socrata_http_ms"] == 650.0
    assert published[-1][0] == "metrics.turn"
    service.on_client_metrics("t1", {"decision_to_audible_ms": 2900})
    assert published[-1][0] == "metrics.client"
    assert service.summary()["browser_audible_p50_ms"] == 2900


def test_unanswered_turn_is_closed_when_next_starts_and_late_events_attach() -> None:
    service = LatencyMetricsService()
    service.start_turn("t1", "respond")
    service.start_turn("t2", "ignore")
    service.annotate("t1", "speech_interrupted")
    assert service.current_turn_id == "t2"
    service.close_without_llm("ignorado")
    assert service.current_turn_id is None


async def test_cache_hits_and_dedupes_inflight() -> None:
    calls = 0

    async def loader() -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return 42

    cache = QueryCache(ttl_s=60, max_entries=10)
    results = await asyncio.gather(*(cache.get_or_load("k", loader) for _ in range(5)))
    assert results == [42] * 5
    assert await cache.get_or_load("k", loader) == 42
    assert calls == 1


async def test_cache_does_not_store_failures_and_expires() -> None:
    now = [0.0]
    cache = QueryCache(ttl_s=10, max_entries=10, clock=lambda: now[0])

    async def boom() -> int:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        await cache.get_or_load("k", boom)

    async def ok() -> int:
        return 1

    assert await cache.get_or_load("k", ok) == 1
    now[0] = 11

    async def fresh() -> int:
        return 2

    assert await cache.get_or_load("k", fresh) == 2


async def test_cache_evicts_oldest() -> None:
    cache = QueryCache(ttl_s=60, max_entries=2)
    for key in ("a", "b", "c"):
        await cache.get_or_load(key, lambda key=key: asyncio.sleep(0, result=key))
    calls = []

    async def reload() -> str:
        calls.append(1)
        return "a2"

    assert await cache.get_or_load("a", reload) == "a2"
    assert calls == [1]
