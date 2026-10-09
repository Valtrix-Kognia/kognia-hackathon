import logging
import time

from livekit.agents import (
    AgentSession,
    AgentStateChangedEvent,
    CloseEvent,
    ConversationItemAddedEvent,
    ErrorEvent,
    UserInputTranscribedEvent,
)
from livekit.agents.llm import ChatMessage

from app.domain.models.emotion_analysis import EmotionAnalysis
from app.emotions.emotion_worker import EmotionWorker
from app.voice.event_publisher import EventPublisher
from app.voice.transcript_tracker import TranscriptTracker

logger = logging.getLogger("kognia.session")

_STATE_EVENTS = {
    "listening": "agent.listening",
    "thinking": "agent.thinking",
    "speaking": "agent.speaking",
}


class SessionObserver:
    """Translates AgentSession events into dashboard events. Handlers never block or raise."""

    def __init__(
        self,
        session: AgentSession,
        events: EventPublisher,
        tracker: TranscriptTracker,
        emotions: EmotionWorker,
        started_at: float,
    ) -> None:
        self._session = session
        self._events = events
        self._tracker = tracker
        self._emotions = emotions
        self._started_at = started_at
        self._speaking_since_ms: int | None = None

    def attach(self) -> None:
        self._session.on("user_input_transcribed", self._on_user_transcribed)
        self._session.on("agent_state_changed", self._on_agent_state)
        self._session.on("conversation_item_added", self._on_item_added)
        self._session.on("error", self._on_error)
        self._session.on("close", self._on_close)

    def on_emotion(self, analysis: EmotionAnalysis) -> None:
        self._events.publish("emotion.analyzed", analysis)

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started_at) * 1000)

    def _on_user_transcribed(self, ev: UserInputTranscribedEvent) -> None:
        segment, new_speaker = self._tracker.on_user_transcript(
            ev.transcript, ev.is_final, ev.speaker_id
        )
        if segment is None:
            return
        self._events.publish(
            "transcript.final" if segment.is_final else "transcript.partial", segment
        )
        if new_speaker:
            self._events.publish(
                "speaker.identified",
                {
                    "speaker_id": segment.speaker_id,
                    "speaker_label": segment.speaker_label,
                    "segment_id": segment.id,
                },
            )
        if segment.is_final:
            self._emotions.submit(segment)

    def _on_agent_state(self, ev: AgentStateChangedEvent) -> None:
        if ev.new_state == "speaking":
            self._speaking_since_ms = self._elapsed_ms()
        event_type = _STATE_EVENTS.get(ev.new_state)
        if event_type:
            self._events.publish(event_type, {"state": ev.new_state})  # type: ignore[arg-type]

    def _on_item_added(self, ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if not isinstance(item, ChatMessage) or item.role != "assistant":
            return
        segment = self._tracker.on_agent_message(
            item.text_content or "", item.interrupted, self._speaking_since_ms
        )
        self._speaking_since_ms = None
        if segment:
            self._events.publish("transcript.final", segment)

    def _on_error(self, ev: ErrorEvent) -> None:
        source = (
            type(ev.source).__module__.split(".")[-1] if ev.source else "desconocido"
        )
        recoverable = bool(getattr(ev.error, "recoverable", False))
        logger.error("session error from %s: %r", source, ev.error)
        self._events.publish(
            "error.occurred",
            {
                "source": source,
                "recoverable": recoverable,
                "message": "Se produjo un error en el servicio de voz."
                + (" Reintentando." if recoverable else ""),
            },
        )

    def _on_close(self, ev: CloseEvent) -> None:
        self._events.publish("session.ended", {"reason": str(ev.reason)})
