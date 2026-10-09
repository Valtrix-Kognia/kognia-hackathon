import asyncio
import contextlib
import logging
from collections.abc import Callable

from app.domain.models.emotion_analysis import EmotionAnalysis
from app.domain.models.transcript_segment import TranscriptSegment
from app.emotions.emotion_analyzer import EmotionAnalyzer

logger = logging.getLogger("kognia.emotions")


class EmotionWorker:
    """Analyzes final segments off the event loop so the voice pipeline is never blocked."""

    def __init__(
        self,
        analyzer_factory: Callable[[], EmotionAnalyzer | None],
        on_result: Callable[[EmotionAnalysis], None],
        max_pending: int = 50,
    ) -> None:
        self._analyzer_factory = analyzer_factory
        self._on_result = on_result
        self._queue: asyncio.Queue[TranscriptSegment | None] = asyncio.Queue(
            maxsize=max_pending
        )
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="kognia-emotion-worker")

    def submit(self, segment: TranscriptSegment) -> None:
        if not segment.is_final:
            return
        try:
            self._queue.put_nowait(segment)
        except asyncio.QueueFull:
            logger.warning("emotion queue full, skipping segment %s", segment.id)

    async def aclose(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        analyzer = await asyncio.to_thread(self._analyzer_factory)
        if analyzer is None:
            logger.error("emotion analyzer unavailable; emotion analysis disabled")
            return
        while (segment := await self._queue.get()) is not None:
            result = await asyncio.to_thread(analyzer.analyze, segment)
            self._on_result(result)
