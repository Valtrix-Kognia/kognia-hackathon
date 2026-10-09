import asyncio

import pytest

from app.infrastructure.socrata.query_cache import QueryCache
from app.voice.latency_metrics import LatencyMetricsService, ToolTiming, percentile


def test_percentile_interpolates() -> None:
    assert percentile([], 50) is None
    assert percentile([100.0], 95) == 100.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5


def test_turn_breakdown_and_first_audio() -> None:
    service = LatencyMetricsService()
    service.on_user_message(
        "m1",
        {
            "end_of_turn_delay": 0.5,
            "transcription_delay": 0.2,
            "stopped_speaking_at": 1000.0,
        },
    )
    service.on_tool(ToolTiming("count_ips", 800.0, cache_hit=False))
    assert service.on_agent_message({}) is None
    service.on_agent_speaking(1001.5)
    payload = service.on_agent_message({"e2e_latency": 3.0, "llm_node_ttft": 0.8})
    assert payload is not None
    assert payload["stages_ms"]["first_audio"] == 1500.0
    assert payload["stages_ms"]["e2e_latency"] == 3000.0
    assert payload["socrata_ms"] == 800.0
    assert payload["summary"]["e2e_p50_ms"] == 3000.0


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
