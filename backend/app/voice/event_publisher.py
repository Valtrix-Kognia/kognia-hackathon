import asyncio
import itertools
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.domain.models.realtime_event import EventType, RealtimeEvent

logger = logging.getLogger("kognia.events")

SendText = Callable[[str], Awaitable[Any]]


class EventPublisher:
    """Serializes dashboard events and sends them in order without blocking the voice pipeline."""

    def __init__(self, session_id: str, send_text: SendText) -> None:
        self._session_id = session_id
        self._send_text = send_text
        self._seq = itertools.count(1)
        self._queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=500)
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(
                self._drain(), name="kognia-event-publisher"
            )

    def publish(
        self, event_type: EventType, payload: BaseModel | dict[str, Any]
    ) -> None:
        data = (
            payload.model_dump(mode="json")
            if isinstance(payload, BaseModel)
            else payload
        )
        event = RealtimeEvent(
            type=event_type,
            session_id=self._session_id,
            seq=next(self._seq),
            emitted_at=datetime.now(UTC),
            payload=data,
        )
        try:
            self._queue.put_nowait(event.model_dump_json())
        except asyncio.QueueFull:
            logger.warning("event queue full, dropping %s", event_type)

    async def aclose(self) -> None:
        if self._task is None:
            return
        await self._queue.put(None)
        try:
            await asyncio.wait_for(self._task, timeout=3)
        except TimeoutError:
            self._task.cancel()
        self._task = None

    async def _drain(self) -> None:
        while (message := await self._queue.get()) is not None:
            try:
                await self._send_text(message)
            except Exception:
                logger.exception("failed to publish dashboard event")
