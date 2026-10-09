import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

Loader = Callable[[], Awaitable[Any]]


class QueryCache:
    """Bounded TTL cache with in-flight de-duplication for successful Socrata responses.

    Concurrent identical queries share one HTTP request; failures are never cached.
    """

    def __init__(
        self,
        ttl_s: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[str, asyncio.Future[Any]] = {}
        self.hits = 0
        self.misses = 0

    async def get_or_load(self, key: str, loader: Loader) -> Any:
        if self._ttl_s <= 0:
            return await loader()
        cached = self._entries.get(key)
        if cached and self._clock() - cached[0] < self._ttl_s:
            self._entries.move_to_end(key)
            self.hits += 1
            return cached[1]
        if key in self._inflight:
            self.hits += 1
            return await asyncio.shield(self._inflight[key])
        self.misses += 1
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            value = await loader()
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()
            raise
        else:
            future.set_result(value)
            self._store(key, value)
            return value
        finally:
            self._inflight.pop(key, None)

    def _store(self, key: str, value: Any) -> None:
        self._entries[key] = (self._clock(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
