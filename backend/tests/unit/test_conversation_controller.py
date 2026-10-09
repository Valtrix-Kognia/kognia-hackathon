from datetime import UTC, datetime

from app.voice.conversation_controller import ConversationController
from app.voice.latency_metrics import LatencyMetricsService
from app.voice.speaker_diarization import SpeakerDiarizationService
from app.voice.speaker_registry import SpeakerRegistry
from app.voice.transcript_tracker import TranscriptTracker
from app.voice.turn_manager import TurnManagementService, TurnMode
from tests.unit.speech_fixtures import alt


class FakeHandle:
    def __init__(self, allow_interruptions: bool) -> None:
        self.id = "speech_1"
        self.allow_interruptions = allow_interruptions
        self.interrupted = False
        self.finished = False

    def done(self) -> bool:
        return self.finished

    def interrupt(self, force: bool = False) -> "FakeHandle":
        self.interrupted = True
        return self


class FakeEvents:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    def publish(self, kind, payload, turn_id=None) -> None:
        data = payload if isinstance(payload, dict) else payload.model_dump()
        self.published.append((kind, data))


class FakeEmotions:
    def submit(self, _segment) -> None:
        pass


def build(handle: FakeHandle) -> tuple[ConversationController, FakeEvents, list[str]]:
    events = FakeEvents()
    controller = ConversationController(
        events,  # type: ignore[arg-type]
        TranscriptTracker("room", SpeakerRegistry(), clock_ms=lambda: 0),
        SpeakerDiarizationService(),
        TurnManagementService(TurnMode.WAKE_WORD),
        FakeEmotions(),  # type: ignore[arg-type]
        LatencyMetricsService(),
        datetime.now(UTC).timestamp(),
    )
    controller.bind_current_speech(lambda: handle)  # type: ignore[arg-type,return-value]
    deferred: list[str] = []
    controller.on_deferred_request(deferred.append)
    return controller, events, deferred


def test_wake_word_interrupts_uninterruptible_speech() -> None:
    handle = FakeHandle(allow_interruptions=False)
    controller, _, deferred = build(handle)
    controller.on_final(alt(("0", "Kognia, ¿cuántas IPS hay en Huila?")))
    assert handle.interrupted
    assert deferred == []


def test_ips_question_during_speech_is_deferred_until_agent_finishes() -> None:
    handle = FakeHandle(allow_interruptions=False)
    controller, events, deferred = build(handle)
    controller.on_final(alt(("0", "¿Cuántas sedes hay en Bogotá?")))
    assert not handle.interrupted
    assert deferred == []
    handle.finished = True
    controller.on_agent_finished_speaking()
    assert deferred == ["¿Cuántas sedes hay en Bogotá?"]
    decision = [p for kind, p in events.published if kind == "turn.decision"][-1]
    assert decision["reason"] == "diferido_mientras_hablaba"


def test_side_talk_during_speech_is_not_deferred() -> None:
    handle = FakeHandle(allow_interruptions=False)
    controller, _, deferred = build(handle)
    controller.on_final(alt(("0", "oye viste el partido de anoche")))
    handle.finished = True
    controller.on_agent_finished_speaking()
    assert deferred == []
