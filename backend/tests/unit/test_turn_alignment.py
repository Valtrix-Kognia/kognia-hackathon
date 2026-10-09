from app.voice.speaker_diarization import SpeakerDiarizationService
from app.voice.turn_alignment import align_to_committed
from tests.unit.speech_fixtures import alt

diarize = SpeakerDiarizationService().analyze


def test_skipped_finals_do_not_leak_into_next_turn() -> None:
    buffered = [
        diarize(alt(("0", "Kognia, necesito que me"))),
        diarize(alt(("0", "digas cuántos prestadores hay"))),
        diarize(alt(("0", "Kognia."))),
    ]
    used, stale = align_to_committed(buffered, "Kognia.")
    assert [u.text for u in used] == ["Kognia."]
    assert len(stale) == 2


def test_multi_final_turn_is_kept_whole() -> None:
    buffered = [
        diarize(alt(("0", "Kognia, ¿cuántas"))),
        diarize(alt(("0", "hay en Caldas?"))),
    ]
    used, stale = align_to_committed(buffered, "Kognia, ¿cuántas hay en Caldas?")
    assert len(used) == 2 and stale == []


def test_empty_commit_keeps_buffer() -> None:
    buffered = [diarize(alt(("0", "hola")))]
    assert align_to_committed(buffered, "") == (buffered, [])
