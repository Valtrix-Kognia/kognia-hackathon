import itertools
from collections.abc import Callable
from datetime import UTC, datetime

from app.domain.models.transcript_segment import TranscriptSegment
from app.voice.speaker_registry import SpeakerRegistry

AGENT_SPEAKER_ID = "agente"
AGENT_SPEAKER_LABEL = "Kognia"


class TranscriptTracker:
    """Turns STT partial/final events into consolidated, ordered transcript segments.

    All partials of an utterance share one segment id; the final event closes that
    segment with the same id so the UI replaces the provisional text in place.
    """

    def __init__(
        self,
        session_id: str,
        speakers: SpeakerRegistry,
        clock_ms: Callable[[], int],
    ) -> None:
        self._session_id = session_id
        self._speakers = speakers
        self._clock_ms = clock_ms
        self._counter = itertools.count(1)
        self._open_id: str | None = None
        self._open_start_ms = 0

    def on_user_transcript(
        self, text: str, is_final: bool, provider_speaker_id: str | None
    ) -> tuple[TranscriptSegment | None, bool]:
        """Return (segment, new_speaker). segment is None for empty transcripts."""
        now = self._clock_ms()
        if not text.strip():
            if is_final:
                self._open_id = None
            return None, False
        if self._open_id is None:
            self._open_id = f"u-{next(self._counter)}"
            self._open_start_ms = now
        if is_final:
            speaker_id, label, is_new = self._speakers.resolve(provider_speaker_id)
        else:
            speaker_id, label = self._speakers.peek(provider_speaker_id)
            is_new = False
        segment = TranscriptSegment(
            id=self._open_id,
            session_id=self._session_id,
            role="user",
            speaker_id=speaker_id,
            speaker_label=label,
            text=text.strip(),
            start_ms=self._open_start_ms,
            end_ms=now,
            is_final=is_final,
            timestamp=datetime.now(UTC),
        )
        if is_final:
            self._open_id = None
        return segment, is_new

    def on_agent_message(
        self, text: str, interrupted: bool, started_ms: int | None = None
    ) -> TranscriptSegment | None:
        if not text.strip():
            return None
        now = self._clock_ms()
        return TranscriptSegment(
            id=f"a-{next(self._counter)}",
            session_id=self._session_id,
            role="agent",
            speaker_id=AGENT_SPEAKER_ID,
            speaker_label=AGENT_SPEAKER_LABEL,
            text=text.strip(),
            start_ms=started_ms if started_ms is not None else now,
            end_ms=now,
            is_final=True,
            interrupted=interrupted,
            timestamp=datetime.now(UTC),
        )
