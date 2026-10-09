from app.voice.speaker_registry import UNKNOWN_SPEAKER_LABEL, SpeakerRegistry
from app.voice.transcript_tracker import TranscriptTracker


class FakeClock:
    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now


def build() -> tuple[TranscriptTracker, FakeClock]:
    clock = FakeClock()
    return TranscriptTracker("room-1", SpeakerRegistry(), clock), clock


def test_partials_share_id_and_final_closes_segment() -> None:
    tracker, clock = build()
    clock.now = 100
    p1, _ = tracker.on_user_transcript("cuántas", False, "0")
    clock.now = 400
    p2, _ = tracker.on_user_transcript("cuántas IPS", False, "0")
    clock.now = 900
    final, new_speaker = tracker.on_user_transcript("¿Cuántas IPS hay?", True, "0")
    assert p1 and p2 and final
    assert p1.id == p2.id == final.id
    assert final.is_final and not p1.is_final
    assert (final.start_ms, final.end_ms) == (100, 900)
    assert new_speaker is True
    next_seg, _ = tracker.on_user_transcript("otra", False, "0")
    assert next_seg and next_seg.id != final.id


def test_speakers_get_stable_labels_in_order_of_appearance() -> None:
    tracker, _ = build()
    a, new_a = tracker.on_user_transcript("hola", True, "0")
    b, new_b = tracker.on_user_transcript("buenas", True, "1")
    c, new_c = tracker.on_user_transcript("de nuevo", True, "0")
    assert (a.speaker_label, b.speaker_label, c.speaker_label) == (
        "Hablante 1",
        "Hablante 2",
        "Hablante 1",
    )
    assert (new_a, new_b, new_c) == (True, True, False)


def test_missing_speaker_is_unknown_not_guessed() -> None:
    tracker, _ = build()
    seg, new = tracker.on_user_transcript("hola", True, None)
    assert seg.speaker_label == UNKNOWN_SPEAKER_LABEL
    assert new is False


def test_empty_transcript_is_ignored() -> None:
    tracker, _ = build()
    seg, _ = tracker.on_user_transcript("   ", False, "0")
    assert seg is None


def test_agent_message_is_role_agent_and_keeps_interrupted_flag() -> None:
    tracker, clock = build()
    clock.now = 2000
    seg = tracker.on_agent_message("En el Quindío hay...", True, started_ms=1500)
    assert seg.role == "agent"
    assert seg.interrupted is True
    assert (seg.start_ms, seg.end_ms) == (1500, 2000)
