import logging

from livekit.agents.stt import SpeechData
from livekit.agents.voice.speech_handle import SpeechHandle

from app.emotions.emotion_worker import EmotionWorker
from app.voice.event_publisher import EventPublisher
from app.voice.speaker_diarization import DiarizedUtterance, SpeakerDiarizationService
from app.voice.transcript_tracker import TranscriptTracker
from app.voice.turn_manager import TurnDecision, TurnManagementService, TurnMode
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
        session_started_wall: float,
    ) -> None:
        self._events = events
        self._tracker = tracker
        self._diarization = diarization
        self._turns = turns
        self._emotions = emotions
        self._session_started_wall = session_started_wall
        self._audio_offset_ms: int | None = None
        self._pending: list[DiarizedUtterance] = []
        self._agent_speech: SpeechHandle | None = None

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
            self._events.publish("transcript.partial", segment)
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
            self._events.publish("transcript.final", segment)
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
        self._maybe_interrupt_for_wake_word(utterance.text)

    def complete_turn(self, committed_text: str) -> TurnDecision:
        utterances, self._pending = self._pending, []
        state = self._turns.follow_up_state()
        decision = self._turns.decide(utterances, committed_text)
        self._events.publish(
            "turn.decision",
            {
                "action": decision.action,
                "reason": decision.reason,
                "mode": decision.mode.value,
                "text": committed_text,
            },
        )
        logger.info(
            "turn decision %s (%s) speakers=%s follow_up=%s",
            decision.action,
            decision.reason,
            sorted({s or "?" for u in utterances for s in u.speakers}),
            state,
        )
        return decision

    def on_agent_speech(self, handle: SpeechHandle) -> None:
        self._agent_speech = handle
        self._apply_interruptibility()

    def on_agent_finished_speaking(self) -> None:
        self._turns.mark_agent_replied()

    def _apply_interruptibility(self) -> None:
        handle = self._agent_speech
        if handle is None or handle.done() or handle.interrupted:
            return
        try:
            handle.allow_interruptions = self._turns.mode is TurnMode.OPEN
        except RuntimeError:
            logger.debug("speech handle no longer accepts interruption changes")

    def _maybe_interrupt_for_wake_word(self, text: str) -> None:
        handle = self._agent_speech
        if (
            self._turns.mode is not TurnMode.WAKE_WORD
            or handle is None
            or handle.done()
            or handle.interrupted
        ):
            return
        if find_wake_word(text).found:
            logger.info("wake word heard while speaking: interrupting agent")
            handle.interrupt(force=True)
