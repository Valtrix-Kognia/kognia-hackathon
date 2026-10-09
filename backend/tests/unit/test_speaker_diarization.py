from app.voice.speaker_diarization import SpeakerDiarizationService
from tests.unit.speech_fixtures import FakeAlternative, alt

service = SpeakerDiarizationService()


def test_single_speaker_is_one_span_with_word_times() -> None:
    u = service.analyze(alt(("0", "cuántas IPS hay en el Quindío")))
    assert len(u.spans) == 1
    assert u.spans[0].speaker_id == "0"
    assert u.spans[0].start_s == 0.0 and u.spans[0].end_s > 1.0
    assert not u.multi_speaker and not u.overlap_suspected


def test_sequential_speakers_are_split_and_flagged_multi_speaker() -> None:
    u = service.analyze(
        alt(
            ("0", "Kognia cuántas IPS hay en Armenia"),
            ("1", "y también en Pereira por favor"),
        )
    )
    assert [s.speaker_id for s in u.spans] == ["0", "1"]
    assert u.multi_speaker
    assert not u.overlap_suspected


def test_single_word_flicker_becomes_unknown_not_reassigned() -> None:
    u = service.analyze(
        alt(("0", "cuántas sedes"), ("1", "hay"), ("0", "en Caldas en total"))
    )
    assert [s.speaker_id for s in u.spans] == ["0", None, "0"]
    assert u.spans[1].text == "hay"


def test_rapid_alternation_is_suspected_overlap() -> None:
    u = service.analyze(
        alt(
            ("0", "cuántas"),
            ("1", "oye mira"),
            ("0", "IPS hay"),
            ("1", "no sé"),
            ("2", "qué"),
        )
    )
    assert u.overlap_suspected


def test_missing_word_speakers_are_unknown() -> None:
    u = service.analyze(alt((None, "hola qué tal")))
    assert u.spans[0].speaker_id is None
    assert u.speakers == set()


def test_without_words_falls_back_to_alternative_speaker() -> None:
    u = service.analyze(
        FakeAlternative(text="hola Kognia", speaker_id="2", end_time=1.0)
    )
    assert u.spans[0].speaker_id == "2"
    assert u.text == "hola Kognia"


def test_low_confidence_is_flagged() -> None:
    u = service.analyze(alt(("0", "algo poco claro aquí"), confidence=0.3))
    assert u.low_confidence
