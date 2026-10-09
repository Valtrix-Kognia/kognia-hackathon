import pytest

from app.voice.speaker_diarization import SpeakerDiarizationService
from app.voice.turn_manager import (
    TurnManagementService,
    TurnMode,
    is_incomplete_request,
)
from app.voice.wake_word import WakeLevel, find_wake_word
from tests.unit.speech_fixtures import alt

diarize = SpeakerDiarizationService().analyze


class Clock:
    def __init__(self) -> None:
        self.now = 50.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("Kognia, ¿cuántas IPS hay?", WakeLevel.CONFIRMED),
        ("Cognia dime", WakeLevel.CONFIRMED),
        ("Cocnea dime cuántas", WakeLevel.PROBABLE),
        ("Cucnia busca hospitales", WakeLevel.PROBABLE),
        ("oye Konia muestra", WakeLevel.PROBABLE),
        ("la compañía tiene sedes", WakeLevel.AMBIGUOUS),
        ("no lo conocía", WakeLevel.AMBIGUOUS),
        ("yo le dije a Kognia que", WakeLevel.AMBIGUOUS),
        ("Colombia tiene muchas IPS", WakeLevel.NONE),
        ("Coña", WakeLevel.NONE),
        ("Corina dime", WakeLevel.NONE),
    ],
)
def test_wake_levels(text: str, level: WakeLevel) -> None:
    assert find_wake_word(text).level is level


@pytest.mark.parametrize(
    ("request_text", "incomplete"),
    [
        ("Necesito que me", True),
        ("cuántas", True),
        ("busca hospitales en", True),
        ("digas cuál es la mejor IPS", False),
        ("¿cuántas IPS hay en Caldas?", False),
        ("busca hospitales en Armenia", False),
        ("", True),
    ],
)
def test_incomplete_request(request_text: str, incomplete: bool) -> None:
    assert is_incomplete_request(request_text) is incomplete


def manager() -> tuple[TurnManagementService, Clock]:
    clock = Clock()
    return TurnManagementService(
        TurnMode.WAKE_WORD, clock=clock, merge_window_s=5
    ), clock


def test_fragmented_request_is_held_then_consolidated() -> None:
    turns, clock = manager()
    first = turns.decide([diarize(alt(("0", "Kognia. Necesito que me")))], "")
    assert (first.action, first.reason) == ("hold", "solicitud_incompleta")
    clock.now += 1.2
    second = turns.decide([diarize(alt(("0", "digas cuál es la mejor IPS")))], "")
    assert (second.action, second.reason) == ("respond", "solicitud_consolidada")
    assert second.llm_text == "Kognia. Necesito que me digas cuál es la mejor IPS"
    assert second.merged_from == (
        "Kognia. Necesito que me",
        "digas cuál es la mejor IPS",
    )


def test_fragments_from_different_speakers_are_not_merged() -> None:
    turns, clock = manager()
    turns.decide([diarize(alt(("0", "Kognia. Necesito que me")))], "")
    clock.now += 1
    other = turns.decide([diarize(alt(("1", "oye ya almorzaste")))], "")
    assert other.action == "ignore"
    assert other.merged_from == ()


def test_held_fragment_expires() -> None:
    turns, clock = manager()
    turns.decide([diarize(alt(("0", "Kognia. Necesito que me")))], "")
    clock.now += 9
    assert (
        turns.decide([diarize(alt(("0", "digas algo bonito")))], "").action == "ignore"
    )


def test_wake_word_alone_listens_without_llm_then_takes_request() -> None:
    turns, clock = manager()
    d = turns.decide([diarize(alt(("0", "Kognia.")))], "")
    assert (d.action, d.activation) == ("listen", "confirmada")
    clock.now += 2
    follow = turns.decide([diarize(alt(("0", "cuántas camas hay en Caldas")))], "")
    assert (follow.action, follow.reason) == ("respond", "solicitud_consolidada")


def test_ambiguous_mention_is_ignored_and_labeled() -> None:
    turns, _ = manager()
    d = turns.decide([diarize(alt(("0", "la compañía tiene sedes nuevas")))], "")
    assert (d.action, d.reason) == ("ignore", "activacion_ambigua")


def test_probable_variant_activates() -> None:
    turns, _ = manager()
    d = turns.decide([diarize(alt(("0", "Cocnea, ¿cuántas IPS hay en Caldas?")))], "")
    assert (d.action, d.activation) == ("respond", "probable")


def test_short_wake_fragment_merges_despite_speaker_id_flip() -> None:
    turns, clock = manager()
    assert turns.decide([diarize(alt(("0", "Kognia.")))], "").action == "listen"
    clock.now += 1.5
    d = turns.decide(
        [diarize(alt(("1", "¿Qué niveles de atención aparecen en los datos?")))], ""
    )
    assert (d.action, d.reason) == ("respond", "solicitud_consolidada")


def test_long_fragment_from_other_speaker_is_not_merged() -> None:
    turns, clock = manager()
    turns.decide(
        [diarize(alt(("0", "Kognia, quisiera saber cuántas sedes hay en")))], ""
    )
    clock.now += 1.5
    d = turns.decide([diarize(alt(("1", "oye ya almorzaste")))], "")
    assert d.action == "ignore"
