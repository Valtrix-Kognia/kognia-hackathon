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


def _with_confidences(*pairs: tuple[str, str, float]):
    a = alt(*[(spk, word) for spk, word, _ in pairs])
    for word, (_, _, conf) in zip(a.words, pairs, strict=True):
        word.confidence = conf
    return a


def test_low_confidence_cluster_from_measured_overlap_is_flagged() -> None:
    measured = _with_confidences(
        ("0", "Kognia", 0.986),
        ("0", "cuántas", 0.952),
        ("0", "IPS", 1.0),
        ("0", "hay", 1.0),
        ("0", "en", 0.999),
        ("0", "el", 0.645),
        ("0", "Yo", 0.715),
        ("1", "saber", 0.785),
        ("1", "qué", 1.0),
    )
    assert service.analyze(measured).overlap_suspected


def test_isolated_low_confidence_word_in_clean_speech_is_not_overlap() -> None:
    measured = _with_confidences(
        ("0", "Kognia", 0.948),
        ("0", "cuántas", 0.936),
        ("0", "IPS", 1.0),
        ("0", "hay", 1.0),
        ("0", "en", 1.0),
        ("0", "el", 0.539),
        ("0", "Quindío", 0.998),
    )
    assert not service.analyze(measured).overlap_suspected


def test_low_confidence_cluster_with_single_speaker_is_not_overlap() -> None:
    clean_live = _with_confidences(
        ("0", "Kognia", 0.71),
        ("0", "cuántas", 0.78),
        ("0", "IPS", 0.95),
        ("0", "hay", 0.99),
        ("0", "en", 0.98),
        ("0", "Caldas", 0.9),
    )
    assert not service.analyze(clean_live).overlap_suspected
