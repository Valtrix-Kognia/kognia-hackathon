import pytest

from app.voice.speaker_diarization import SpeakerDiarizationService
from app.voice.turn_manager import TurnManagementService, TurnMode
from app.voice.wake_word import find_wake_word
from tests.unit.speech_fixtures import alt

diarize = SpeakerDiarizationService().analyze


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def manager(mode: TurnMode) -> tuple[TurnManagementService, Clock]:
    clock = Clock()
    labels = {"0": "Hablante 1", "1": "Hablante 2"}
    return (
        TurnManagementService(
            mode=mode,
            follow_up_window_s=8,
            clock=clock,
            label_for=lambda s: labels.get(s or "", "Hablante desconocido"),
        ),
        clock,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kognia, ¿cuántas IPS hay en Armenia?", "¿cuántas IPS hay en Armenia?"),
        ("oye cognia compara Quindío con Risaralda", "compara Quindío con Risaralda"),
        ("Konia muéstrame las públicas", "muéstrame las públicas"),
    ],
)
def test_wake_word_variants(text: str, expected: str) -> None:
    match = find_wake_word(text)
    assert match.found and match.request == expected


def test_wake_word_not_found_in_normal_talk() -> None:
    assert not find_wake_word("¿vamos a almorzar después de la demo?").found
    assert not find_wake_word("la compañía tiene sedes").found


def test_wake_mode_ignores_conversation_not_addressed() -> None:
    turns, _ = manager(TurnMode.WAKE_WORD)
    d = turns.decide([diarize(alt(("0", "oye y cuántas personas vienen hoy")))], "")
    assert (d.action, d.reason) == ("ignore", "no_dirigido_a_kognia")


def test_wake_mode_answers_and_allows_same_speaker_follow_up() -> None:
    turns, clock = manager(TurnMode.WAKE_WORD)
    d = turns.decide([diarize(alt(("0", "Kognia cuántas IPS hay en Caldas")))], "")
    assert (d.action, d.addressed_speaker) == ("respond", "0")
    turns.mark_agent_replied()
    clock.now += 3
    follow = turns.decide([diarize(alt(("0", "y cuántas son públicas")))], "")
    assert (follow.action, follow.reason) == ("respond", "seguimiento")
    other = turns.decide([diarize(alt(("1", "y en Risaralda cuántas hay")))], "")
    assert other.action == "ignore"


def test_follow_up_window_expires() -> None:
    turns, clock = manager(TurnMode.WAKE_WORD)
    turns.decide([diarize(alt(("0", "Kognia cuántas IPS hay")))], "")
    turns.mark_agent_replied()
    clock.now += 20
    assert (
        turns.decide([diarize(alt(("0", "y cuántas son públicas")))], "").action
        == "ignore"
    )


def test_overlap_asks_to_repeat_in_any_mode() -> None:
    for mode in TurnMode:
        turns, _ = manager(mode)
        overlapped = diarize(
            alt(
                ("0", "Kognia cuántas"),
                ("1", "oye mira"),
                ("0", "IPS hay"),
                ("1", "no sé"),
            )
        )
        d = turns.decide([overlapped], "")
        assert (d.action, d.reason) == ("ask_repeat", "habla_superpuesta")


def test_backchannel_is_ignored_even_in_open_mode() -> None:
    turns, _ = manager(TurnMode.OPEN)
    assert turns.decide([diarize(alt(("0", "sí claro")))], "").reason == "muletilla"


def test_open_mode_labels_speakers_for_llm_when_several_spoke() -> None:
    turns, _ = manager(TurnMode.OPEN)
    d = turns.decide(
        [
            diarize(
                alt(
                    ("0", "cuántas IPS hay en Armenia"),
                    ("1", "y también en Pereira por favor"),
                )
            )
        ],
        "",
    )
    assert d.action == "respond"
    assert d.llm_text.startswith("[Hablante 1] cuántas IPS hay en Armenia [Hablante 2]")


def test_empty_turn_ignored_and_fallback_text_used() -> None:
    turns, _ = manager(TurnMode.OPEN)
    assert turns.decide([], "").action == "ignore"
    assert turns.decide([], "¿Cuántas IPS hay?").action == "respond"


def test_switching_mode_resets_follow_up() -> None:
    turns, _ = manager(TurnMode.WAKE_WORD)
    turns.decide([diarize(alt(("0", "Kognia hola")))], "")
    turns.mark_agent_replied()
    turns.set_mode(TurnMode.WAKE_WORD)
    assert turns.decide([diarize(alt(("0", "y cuántas hay")))], "").action == "ignore"


def test_wake_mode_ignores_overlapped_side_conversation_instead_of_asking() -> None:
    turns, _ = manager(TurnMode.WAKE_WORD)
    overlapped = diarize(
        alt(("0", "oye"), ("1", "mira eso"), ("0", "ya"), ("1", "no sé"), ("2", "qué"))
    )
    assert turns.decide([overlapped], "").action == "ignore"


def test_greeting_does_not_open_follow_up_window() -> None:
    turns, _ = manager(TurnMode.WAKE_WORD)
    turns.mark_agent_replied()
    d = turns.decide([diarize(alt(("0", "ya almorzaron todavía no")))], "")
    assert (d.action, d.reason) == ("ignore", "no_dirigido_a_kognia")


def test_ignored_turn_does_not_open_follow_up_window() -> None:
    turns, _ = manager(TurnMode.WAKE_WORD)
    turns.decide([diarize(alt(("0", "oye y cuántas personas vienen")))], "")
    turns.mark_agent_replied()
    assert (
        turns.decide([diarize(alt(("0", "y cuántas son públicas")))], "").action
        == "ignore"
    )


def test_follow_up_window_counts_from_end_of_last_reply_speech() -> None:
    turns, clock = manager(TurnMode.WAKE_WORD)
    turns.decide([diarize(alt(("0", "Kognia cuántas IPS hay en Caldas")))], "")
    turns.mark_agent_replied()
    clock.now += 7
    turns.mark_agent_replied()
    clock.now += 5
    assert (
        turns.decide([diarize(alt(("0", "y cuántas son públicas")))], "").action
        == "respond"
    )


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuántas IPS hay en Caldas?",
        "busca hospitales en Armenia",
        "y cuántas camas hay en Pereira",
    ],
)
def test_wake_mode_answers_clear_domain_request_when_wake_word_was_clipped(
    text: str,
) -> None:
    turns, _ = manager(TurnMode.WAKE_WORD)
    d = turns.decide([diarize(alt(("0", text)))], "")
    assert (d.action, d.reason) == ("respond", "pregunta_sobre_ips")


@pytest.mark.parametrize(
    "text",
    [
        "¿Alguien tiene el cargador del portátil?",
        "el hospital queda lejos de mi casa",
        "¿Ya almorzaron?",
    ],
)
def test_wake_mode_still_ignores_side_talk(text: str) -> None:
    turns, _ = manager(TurnMode.WAKE_WORD)
    assert turns.decide([diarize(alt(("0", text)))], "").action == "ignore"
