import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.application.services.text_matching import normalize
from app.voice.speaker_diarization import DiarizedUtterance
from app.voice.wake_word import find_wake_word

REPEAT_REQUEST = (
    "Escuché varias personas al mismo tiempo y no pude identificar claramente la "
    "pregunta. ¿Podrías repetirla?"
)
UNCLEAR_REQUEST = "No te entendí bien. ¿Podrías repetir la pregunta?"

_BACKCHANNELS = {
    "SI",
    "NO",
    "OK",
    "OKAY",
    "AJA",
    "MMM",
    "MM",
    "EH",
    "AH",
    "BUENO",
    "VALE",
    "CLARO",
    "GRACIAS",
    "LISTO",
    "AHA",
    "UHM",
    "HMM",
    "PERFECTO",
}

_DOMAIN_TERMS = {
    "IPS",
    "PRESTADOR",
    "PRESTADORES",
    "SEDE",
    "SEDES",
    "HOSPITAL",
    "HOSPITALES",
    "CLINICA",
    "CLINICAS",
    "CAMA",
    "CAMAS",
    "AMBULANCIA",
    "AMBULANCIAS",
    "CONSULTORIO",
    "CONSULTORIOS",
    "REPS",
    "INSTITUCIONES",
    "CAPACIDAD",
}
_REQUEST_STARTS = (
    "CUANT",
    "QUE",
    "CUAL",
    "DONDE",
    "COMO",
    "BUSCA",
    "MUESTRA",
    "DIME",
    "COMPARA",
    "LISTA",
    "Y CUANT",
    "Y QUE",
    "Y EN",
)

Action = Literal["respond", "ignore", "ask_repeat"]


class TurnMode(StrEnum):
    OPEN = "open"
    WAKE_WORD = "wake_word"


@dataclass(frozen=True)
class TurnDecision:
    action: Action
    reason: str
    mode: TurnMode
    llm_text: str
    addressed_speaker: str | None = None


class TurnManagementService:
    """Decides whether a completed user turn is answered, ignored or needs repetition.

    Inputs are the diarized final transcripts collected for the turn. The policy:
    - Overlapped or very low-confidence speech is never answered with guesses: ask to repeat.
    - Wake-word mode only answers turns that say "Kognia", or follow-ups from the same
      speaker shortly after Kognia replied; other conversation is transcribed but ignored.
    - Lone backchannels ("sí", "ok") never trigger a reply.
    """

    def __init__(
        self,
        mode: TurnMode = TurnMode.WAKE_WORD,
        follow_up_window_s: float = 8.0,
        clock: Callable[[], float] = time.monotonic,
        label_for: Callable[[str | None], str] = lambda s: s or "desconocido",
    ) -> None:
        self.mode = mode
        self._label_for = label_for
        self._follow_up_window_s = follow_up_window_s
        self._clock = clock
        self._last_reply_at: float | None = None
        self._last_addressed_speaker: str | None = None
        self._answering = False

    def follow_up_state(self) -> dict[str, object]:
        since = (
            None
            if self._last_reply_at is None
            else round(self._clock() - self._last_reply_at, 1)
        )
        return {
            "since_reply_s": since,
            "addressed_speaker": self._last_addressed_speaker,
        }

    def set_mode(self, mode: TurnMode) -> None:
        self.mode = mode
        self._last_reply_at = None
        self._answering = False

    def mark_agent_replied(self) -> None:
        """(Re)starts the follow-up window each time a reply to an addressed turn ends
        speaking (a filler phrase and the answer are separate speeches)."""
        if self._answering:
            self._last_reply_at = self._clock()

    def decide(
        self, utterances: list[DiarizedUtterance], fallback_text: str
    ) -> TurnDecision:
        decision = self._decide(utterances, fallback_text)
        self._answering = decision.action == "respond"
        return decision

    def _decide(
        self, utterances: list[DiarizedUtterance], fallback_text: str
    ) -> TurnDecision:
        text = (
            " ".join(u.text for u in utterances if u.text).strip()
            or fallback_text.strip()
        )
        if not text:
            return TurnDecision("ignore", "transcripcion_vacia", self.mode, "")

        wake = find_wake_word(text)
        domain_request = _is_domain_request(text)
        addressed_turn = (
            self.mode is TurnMode.OPEN
            or wake.found
            or domain_request
            or self._is_follow_up(utterances)
        )
        if not addressed_turn:
            return TurnDecision("ignore", "no_dirigido_a_kognia", self.mode, text)

        if any(u.overlap_suspected for u in utterances):
            return TurnDecision("ask_repeat", "habla_superpuesta", self.mode, text)
        if utterances and all(u.low_confidence for u in utterances):
            return TurnDecision("ask_repeat", "baja_confianza", self.mode, text)
        if not wake.found and _is_backchannel(text):
            return TurnDecision("ignore", "muletilla", self.mode, text)

        addressed = self._speaker_of_wake_word(utterances) if wake.found else None
        if self.mode is TurnMode.WAKE_WORD:
            if wake.found:
                self._last_addressed_speaker = addressed
                if not wake.request:
                    return TurnDecision(
                        "respond", "solo_palabra_activacion", self.mode, text, addressed
                    )
                return TurnDecision(
                    "respond",
                    "palabra_activacion",
                    self.mode,
                    self._labeled(utterances, text),
                    addressed,
                )
            if self._is_follow_up(utterances):
                return TurnDecision(
                    "respond",
                    "seguimiento",
                    self.mode,
                    self._labeled(utterances, text),
                    self._last_addressed_speaker,
                )
            if domain_request:
                speakers = {sp for u in utterances for sp in u.speakers}
                self._last_addressed_speaker = (
                    next(iter(speakers)) if len(speakers) == 1 else None
                )
                return TurnDecision(
                    "respond",
                    "pregunta_sobre_ips",
                    self.mode,
                    self._labeled(utterances, text),
                    self._last_addressed_speaker,
                )
            return TurnDecision("ignore", "no_dirigido_a_kognia", self.mode, text)

        if wake.found:
            self._last_addressed_speaker = addressed
        return TurnDecision(
            "respond",
            "conversacion_abierta",
            self.mode,
            self._labeled(utterances, text),
            addressed,
        )

    def _is_follow_up(self, utterances: list[DiarizedUtterance]) -> bool:
        if (
            self._last_reply_at is None
            or self._clock() - self._last_reply_at > self._follow_up_window_s
        ):
            return False
        speakers = {s for u in utterances for s in u.speakers}
        if self._last_addressed_speaker is None or not speakers:
            return len(speakers) <= 1
        return speakers == {self._last_addressed_speaker}

    @staticmethod
    def _speaker_of_wake_word(utterances: list[DiarizedUtterance]) -> str | None:
        for utterance in utterances:
            for span in utterance.spans:
                if find_wake_word(span.text).found:
                    return span.speaker_id
        return None

    def _labeled(self, utterances: list[DiarizedUtterance], text: str) -> str:
        """Prefix speaker ids when several people spoke, so the LLM sees who asked what."""
        if not any(u.multi_speaker for u in utterances):
            return text
        parts = [
            f"[{self._label_for(s.speaker_id)}] {s.text}"
            for u in utterances
            for s in u.spans
        ]
        return " ".join(parts)


def _is_domain_request(text: str) -> bool:
    """A question or command about the dataset's subject, even if STT clipped "Kognia"."""
    norm = normalize(text)
    tokens = set(norm.split())
    asks = "?" in text or norm.startswith(_REQUEST_STARTS)
    return asks and bool(tokens & _DOMAIN_TERMS)


def _is_backchannel(text: str) -> bool:
    tokens = normalize(text).split()
    return 0 < len(tokens) <= 2 and all(t in _BACKCHANNELS for t in tokens)
