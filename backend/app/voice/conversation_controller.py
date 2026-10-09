import itertools
import logging
from collections.abc import Callable

from livekit.agents.stt import SpeechData
from livekit.agents.voice.speech_handle import SpeechHandle

from app.emotions.emotion_worker import EmotionWorker
from app.voice.event_publisher import EventPublisher
from app.voice.latency_metrics import LatencyMetricsService
from app.voice.speaker_diarization import DiarizedUtterance, SpeakerDiarizationService
from app.voice.transcript_tracker import TranscriptTracker
from app.voice.turn_alignment import align_to_committed
from app.voice.turn_manager import (
    TurnDecision,
    TurnManagementService,
    TurnMode,
    is_domain_request,
)
from app.voice.wake_word import find_wake_word

logger = logging.getLogger("kognia.conversation")


class ConversationController:
    """Owns the shared-microphone conversation state for one session.

    STT events arrive from the agent's stt_node; completed turns are gated by the
    TurnManagementService; agent speech interruptibility follows the active turn mode.
    """

    def __init__(
        self,
        events: EventPublisher,
        tracker: TranscriptTracker,
        diarization: SpeakerDiarizationService,
        turns: TurnManagementService,
        emotions: EmotionWorker,
        latency: LatencyMetricsService,
        session_started_wall: float,
    ) -> None:
        self._events = events
        self._tracker = tracker
        self._diarization = diarization
        self._turns = turns
        self._emotions = emotions
        self._latency = latency
        self._turn_counter = itertools.count(1)
        self._session_started_wall = session_started_wall
        self._audio_offset_ms: int | None = None
        self._pending: list[DiarizedUtterance] = []
        self._agent_speech: SpeechHandle | None = None
        self._current_speech: Callable[[], SpeechHandle | None] = lambda: (
            self._agent_speech
        )
        self._deferred: list[str] = []
        self.last_request_text = ""
        self._deferred_handler: Callable[[str], None] = lambda _text: None

    def on_deferred_request(self, handler: Callable[[str], None]) -> None:
        """Called with a request asked while Kognia spoke, once it finishes speaking."""
        self._deferred_handler = handler

    def bind_current_speech(self, provider: Callable[[], SpeechHandle | None]) -> None:
        """Use the session's authoritative current speech for interruption decisions."""
        self._current_speech = provider

    @property
    def turns(self) -> TurnManagementService:
        return self._turns

    @property
    def current_turn_id(self) -> str | None:
        return self._latency.current_turn_id

    @property
    def mode(self) -> TurnMode:
        return self._turns.mode

    def set_mode(self, mode: TurnMode) -> None:
        if mode is self._turns.mode:
            return
        self._turns.set_mode(mode)
        self._apply_interruptibility()
        self._events.publish("turn.mode", {"mode": mode.value})

    def on_audio_started(self, wall_time: float) -> None:
        self._audio_offset_ms = int((wall_time - self._session_started_wall) * 1000)

    def on_interim(self, alternative: SpeechData) -> None:
        segment, _ = self._tracker.on_user_transcript(
            alternative.text, False, alternative.speaker_id
        )
        if segment:
            self._events.publish("transcript.partial", segment, turn_id=None)
        self._maybe_interrupt_for_wake_word(alternative.text)

    def on_final(self, alternative: SpeechData) -> None:
        utterance = self._diarization.analyze(alternative)
        if not utterance.text:
            self._tracker.on_user_transcript("", True, None)
            return
        self._pending.append(utterance)
        for segment, new_speaker in self._tracker.on_diarized_final(
            utterance, self._audio_offset_ms
        ):
            self._events.publish("transcript.final", segment, turn_id=None)
            if new_speaker:
                self._events.publish(
                    "speaker.identified",
                    {
                        "speaker_id": segment.speaker_id,
                        "speaker_label": segment.speaker_label,
                        "segment_id": segment.id,
                    },
                )
            self._emotions.submit(segment)
        if not self._maybe_interrupt_for_wake_word(utterance.text):
            self._maybe_defer(utterance)

    def complete_turn(self, committed_text: str) -> TurnDecision:
        buffered, self._pending = self._pending, []
        utterances, stale = align_to_committed(buffered, committed_text)
        if stale:
            self._report_skipped(stale)
        state = self._turns.follow_up_state()
        decision = self._turns.decide(utterances, committed_text)
        if decision.action == "respond":
            self.last_request_text = decision.llm_text or committed_text
        turn_id = f"t{next(self._turn_counter)}"
        self._latency.start_turn(turn_id, decision.action)
        self._latency.mark("decision")
        self._events.publish(
            "turn.decision",
            {
                "turn_id": turn_id,
                "action": decision.action,
                "reason": decision.reason,
                "mode": decision.mode.value,
                "activation": decision.activation,
                "text": committed_text,
                "merged_from": list(decision.merged_from),
            },
            turn_id=turn_id,
        )
        if decision.action in ("ignore", "hold"):
            self._latency.close_without_llm(
                "ignorado" if decision.action == "ignore" else "retenido"
            )
        logger.info(
            "turn decision %s %s (%s) activation=%s speakers=%s follow_up=%s",
            turn_id,
            decision.action,
            decision.reason,
            decision.activation,
            sorted({s or "?" for u in utterances for s in u.speakers}),
            state,
        )
        return decision

    def _report_skipped(self, stale: list[DiarizedUtterance]) -> None:
        text = " ".join(u.text for u in stale)
        logger.info(
            "discarding %d STT finals not part of the committed turn: %s",
            len(stale),
            text,
        )
        self._events.publish(
            "turn.decision",
            {
                "turn_id": None,
                "action": "ignore",
                "reason": "omitido_mientras_hablaba",
                "mode": self._turns.mode.value,
                "activation": find_wake_word(text).level.value,
                "text": text,
                "merged_from": [],
            },
            turn_id=None,
        )

    def on_agent_speech(self, handle: SpeechHandle) -> None:
        self._agent_speech = handle
        self._apply_interruptibility()

    def on_agent_finished_speaking(self) -> None:
        self._turns.mark_agent_replied()
        if self._deferred and not self._speaking_uninterruptible():
            text = " ".join(self._deferred)
            self._deferred = []
            self.start_programmatic_turn(text, "diferido_mientras_hablaba")
            self._deferred_handler(text)

    def start_programmatic_turn(self, text: str, reason: str) -> str:
        """Open a traced turn for a reply that does not go through a LiveKit commit."""
        turn_id = f"t{next(self._turn_counter)}"
        self.last_request_text = text
        self._latency.start_turn(turn_id, "respond")
        self._latency.mark("decision")
        self._events.publish(
            "turn.decision",
            {
                "turn_id": turn_id,
                "action": "respond",
                "reason": reason,
                "mode": self._turns.mode.value,
                "activation": find_wake_word(text).level.value,
                "text": text,
                "merged_from": [],
            },
            turn_id=turn_id,
        )
        logger.info("turn decision %s respond (%s): %s", turn_id, reason, text)
        return turn_id

    def _apply_interruptibility(self) -> None:
        handle = self._agent_speech
        if handle is None or handle.done() or handle.interrupted:
            return
        try:
            handle.allow_interruptions = self._turns.mode is TurnMode.OPEN
        except RuntimeError:
            logger.debug("speech handle no longer accepts interruption changes")

    def _maybe_interrupt_for_wake_word(self, text: str) -> bool:
        if self._turns.mode is not TurnMode.WAKE_WORD or not find_wake_word(text).found:
            return False
        handle = self._current_speech()
        if handle is None or handle.done() or handle.interrupted:
            return False
        logger.info("wake word heard while speaking: interrupting speech %s", handle.id)
        self._latency.annotate(self._latency.current_turn_id, "wake_word_interrupt")
        handle.interrupt(force=True)
        return True

    def _speaking_uninterruptible(self) -> bool:
        handle = self._current_speech()
        return (
            handle is not None
            and not handle.done()
            and not handle.interrupted
            and not handle.allow_interruptions
        )

    def _maybe_defer(self, utterance: DiarizedUtterance) -> None:
        if (
            self._turns.mode is TurnMode.WAKE_WORD
            and self._speaking_uninterruptible()
            and is_domain_request(utterance.text)
            and not utterance.overlap_suspected
        ):
            self._deferred.append(utterance.text)
            if utterance in self._pending:
                self._pending.remove(utterance)
            logger.info("deferring request heard while speaking: %s", utterance.text)
