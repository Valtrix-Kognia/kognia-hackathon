import logging
import time

from livekit.agents import (
    AgentSession,
    AgentStateChangedEvent,
    CloseEvent,
    ConversationItemAddedEvent,
    ErrorEvent,
    SpeechCreatedEvent,
)
from livekit.agents.llm import ChatMessage

from app.domain.models.emotion_analysis import EmotionAnalysis
from app.voice.conversation_controller import ConversationController
from app.voice.event_publisher import EventPublisher
from app.voice.latency_metrics import LatencyMetricsService
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
        controller: ConversationController,
        latency: LatencyMetricsService,
        started_at: float,
    ) -> None:
        self._session = session
        self._events = events
        self._tracker = tracker
        self._controller = controller
        self._latency = latency
        self._started_at = started_at
        self._speaking_since_ms: int | None = None

    def attach(self) -> None:
        self._session.on("speech_created", self._on_speech_created)
        self._session.on("agent_state_changed", self._on_agent_state)
        self._session.on("conversation_item_added", self._on_item_added)
        self._session.on("error", self._on_error)
        self._session.on("close", self._on_close)

    def on_emotion(self, analysis: EmotionAnalysis) -> None:
        self._events.publish("emotion.analyzed", analysis)

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started_at) * 1000)

    def _on_speech_created(self, ev: SpeechCreatedEvent) -> None:
        self._controller.on_agent_speech(ev.speech_handle)

    def _on_agent_state(self, ev: AgentStateChangedEvent) -> None:
        if ev.new_state == "speaking":
            self._speaking_since_ms = self._elapsed_ms()
            self._latency.on_agent_speaking(ev.created_at)
        elif ev.old_state == "speaking":
            self._controller.on_agent_finished_speaking()
        event_type = _STATE_EVENTS.get(ev.new_state)
        if event_type:
            self._events.publish(event_type, {"state": ev.new_state})  # type: ignore[arg-type]

    def _on_item_added(self, ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if not isinstance(item, ChatMessage):
            return
        if item.role == "user":
            self._latency.on_user_message(item.id, dict(item.metrics))
            return
        if item.role != "assistant":
            return
        turn_metrics = self._latency.on_agent_message(dict(item.metrics))
        if turn_metrics:
            self._events.publish("metrics.turn", turn_metrics)
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
