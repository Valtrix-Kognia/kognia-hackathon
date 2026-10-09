import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.application.services.text_matching import normalize
from app.voice.speaker_diarization import DiarizedUtterance
from app.voice.wake_word import WakeLevel, WakeWordDetector

REPEAT_REQUEST = (
    "Escuché varias personas al mismo tiempo y no pude identificar claramente la "
    "pregunta. ¿Podrías repetirla?"
)
UNCLEAR_REQUEST = "No te entendí bien. ¿Podrías repetir la pregunta?"
LISTENING_ACK = "Te escucho."

_BACKCHANNELS = {
    "SI", "NO", "OK", "OKAY", "AJA", "MMM", "MM", "EH", "AH", "BUENO", "VALE",
    "CLARO", "GRACIAS", "LISTO", "AHA", "UHM", "HMM", "PERFECTO",
}  # fmt: skip
_DOMAIN_TERMS = {
    "IPS", "PRESTADOR", "PRESTADORES", "SEDE", "SEDES", "HOSPITAL", "HOSPITALES",
    "CLINICA", "CLINICAS", "CAMA", "CAMAS", "AMBULANCIA", "AMBULANCIAS",
    "CONSULTORIO", "CONSULTORIOS", "REPS", "INSTITUCIONES", "CAPACIDAD",
}  # fmt: skip
_REQUEST_STARTS = (
    "CUANT", "QUE", "CUAL", "DONDE", "COMO", "BUSCA", "MUESTRA", "DIME",
    "COMPARA", "LISTA", "Y CUANT", "Y QUE", "Y EN",
)  # fmt: skip
_TRAILING_INCOMPLETE = {
    "QUE", "ME", "TE", "SE", "LE", "LES", "LO", "LA", "LOS", "LAS", "EL", "UN", "UNA",
    "UNOS", "UNAS", "DE", "DEL", "AL", "A", "EN", "CON", "POR", "PARA", "Y", "O", "PERO",
    "SI", "MI", "TU", "SU", "MIS", "SUS", "CUAL", "CUALES", "CUANTAS", "CUANTOS", "DONDE",
    "COMO", "MAS", "MENOS", "ENTRE", "SOBRE", "HAY", "ES", "SON", "ESTA", "ESTAN",
    "NECESITO", "QUIERO", "QUISIERA", "DIME", "DIGAS", "SABER", "BUSCA", "BUSCAME",
    "MUESTRAME", "COMPARA", "CUENTAME", "EH", "ESTE", "PUES",
}  # fmt: skip

Action = Literal["respond", "ignore", "ask_repeat", "hold", "listen"]


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
    activation: str = WakeLevel.NONE.value
    merged_from: tuple[str, ...] = ()


@dataclass(frozen=True)
class PendingRequest:
    """An activation waiting for the rest of the request ("Kognia." or a cut sentence)."""

    text: str
    speaker: str | None
    at: float
    wake_only: bool


class TurnManagementService:
    """Decides whether a completed user turn is answered, held, ignored or needs repetition.

    - Overlapped or very low-confidence speech is never answered with guesses.
    - Wake-word mode answers "Kognia ..." (confirmed or probable), clear IPS questions and
      follow-ups from the same speaker shortly after a reply; other talk is ignored.
    - "Kognia" alone opens a listening window without calling the LLM.
    - A cut request ("Kognia, necesito que me") is held and merged with the next turn of
      the same speaker instead of being answered half-way. Different speakers are never
      merged.
    """

    def __init__(
        self,
        mode: TurnMode = TurnMode.WAKE_WORD,
        follow_up_window_s: float = 8.0,
        clock: Callable[[], float] = time.monotonic,
        label_for: Callable[[str | None], str] = lambda s: s or "desconocido",
        merge_window_s: float = 5.0,
        listen_window_s: float = 6.0,
        wake_detector: WakeWordDetector | None = None,
    ) -> None:
        self.mode = mode
        self._label_for = label_for
        self._follow_up_window_s = follow_up_window_s
        self._merge_window_s = merge_window_s
        self._listen_window_s = listen_window_s
        self._clock = clock
        self._wake = wake_detector or WakeWordDetector()
        self._last_reply_at: float | None = None
        self._last_addressed_speaker: str | None = None
        self._answering = False
        self._pending: PendingRequest | None = None

    @property
    def merge_window_s(self) -> float:
        return self._merge_window_s

    def follow_up_state(self) -> dict[str, object]:
        since = (
            None
            if self._last_reply_at is None
            else round(self._clock() - self._last_reply_at, 1)
        )
        return {
            "since_reply_s": since,
            "addressed_speaker": self._last_addressed_speaker,
            "pending": self._pending.text if self._pending else None,
        }

    def set_mode(self, mode: TurnMode) -> None:
        self.mode = mode
        self._last_reply_at = None
        self._answering = False
        self._pending = None

    def mark_agent_replied(self) -> None:
        """(Re)starts the follow-up window each time a reply to an addressed turn ends
        speaking (a filler phrase and the answer are separate speeches)."""
        if self._answering:
            self._last_reply_at = self._clock()

    def take_pending(self) -> PendingRequest | None:
        pending, self._pending = self._pending, None
        return pending

    def decide(
        self, utterances: list[DiarizedUtterance], fallback_text: str
    ) -> TurnDecision:
        decision = self._decide(utterances, fallback_text)
        self._answering = decision.action == "respond"
        return decision

    def _decide(
        self, utterances: list[DiarizedUtterance], fallback_text: str
    ) -> TurnDecision:
        current = (
            " ".join(u.text for u in utterances if u.text).strip()
            or fallback_text.strip()
        )
        if not current:
            return TurnDecision("ignore", "transcripcion_vacia", self.mode, "")
        speakers = {s for u in utterances for s in u.speakers}
        pending = self._continuation_of_pending(speakers)
        text = f"{pending.text} {current}".strip() if pending else current
        merged_from = (pending.text, current) if pending else ()

        wake = self._wake.detect(text)
        domain_request = _is_domain_request(text)
        addressed_turn = (
            self.mode is TurnMode.OPEN
            or wake.found
            or pending is not None
            or domain_request
            or self._is_follow_up(speakers)
        )
        if not addressed_turn:
            reason = (
                "activacion_ambigua"
                if wake.level is WakeLevel.AMBIGUOUS
                else "no_dirigido_a_kognia"
            )
            return TurnDecision(
                "ignore", reason, self.mode, text, activation=wake.level
            )

        if any(u.overlap_suspected for u in utterances):
            return TurnDecision(
                "ask_repeat",
                "habla_superpuesta",
                self.mode,
                text,
                activation=wake.level,
            )
        if utterances and all(u.low_confidence for u in utterances):
            return TurnDecision(
                "ask_repeat", "baja_confianza", self.mode, text, activation=wake.level
            )
        if not wake.found and pending is None and _is_backchannel(text):
            return TurnDecision("ignore", "muletilla", self.mode, text)

        speaker = self._speaker_of_wake_word(utterances) if wake.found else None
        speaker = speaker or (next(iter(speakers)) if len(speakers) == 1 else None)
        request = wake.request if wake.found else text

        if not request.strip():
            self._pending = PendingRequest(text, speaker, self._clock(), wake_only=True)
            return TurnDecision(
                "listen",
                "solo_palabra_activacion",
                self.mode,
                text,
                speaker,
                wake.level,
            )
        if is_incomplete_request(request):
            self._pending = PendingRequest(
                text, speaker, self._clock(), wake_only=False
            )
            return TurnDecision(
                "hold", "solicitud_incompleta", self.mode, text, speaker, wake.level,
                merged_from,
            )  # fmt: skip

        if wake.found or pending or domain_request:
            self._last_addressed_speaker = speaker
        reason = self._respond_reason(wake.found, pending, domain_request, speakers)
        return TurnDecision(
            "respond",
            reason,
            self.mode,
            self._labeled(utterances, text, pending),
            speaker if speaker is not None else self._last_addressed_speaker,
            wake.level,
            merged_from,
        )

    def _respond_reason(
        self,
        wake_found: bool,
        pending: PendingRequest | None,
        domain_request: bool,
        speakers: set[str],
    ) -> str:
        if pending is not None:
            return "solicitud_consolidada"
        if self.mode is TurnMode.OPEN:
            return "conversacion_abierta"
        if wake_found:
            return "palabra_activacion"
        if self._is_follow_up(speakers):
            return "seguimiento"
        return "pregunta_sobre_ips" if domain_request else "conversacion_abierta"

    def _continuation_of_pending(self, speakers: set[str]) -> PendingRequest | None:
        pending, self._pending = self._pending, None
        if pending is None:
            return None
        window = self._listen_window_s if pending.wake_only else self._merge_window_s
        if self._clock() - pending.at > window:
            return None
        if pending.speaker is not None and speakers and speakers != {pending.speaker}:
            return None
        return pending

    def _is_follow_up(self, speakers: set[str]) -> bool:
        if (
            self._last_reply_at is None
            or self._clock() - self._last_reply_at > self._follow_up_window_s
        ):
            return False
        if self._last_addressed_speaker is None or not speakers:
            return len(speakers) <= 1
        return speakers == {self._last_addressed_speaker}

    def _speaker_of_wake_word(self, utterances: list[DiarizedUtterance]) -> str | None:
        for utterance in utterances:
            for span in utterance.spans:
                if self._wake.detect(span.text).found:
                    return span.speaker_id
        return None

    def _labeled(
        self,
        utterances: list[DiarizedUtterance],
        text: str,
        pending: PendingRequest | None,
    ) -> str:
        """Prefix speaker labels when several people spoke, so the LLM sees who asked."""
        if pending is not None or not any(u.multi_speaker for u in utterances):
            return text
        parts = [
            f"[{self._label_for(s.speaker_id)}] {s.text}"
            for u in utterances
            for s in u.spans
        ]
        return " ".join(parts)


def is_incomplete_request(request: str) -> bool:
    """A request cut by end-of-turn: it trails off in a function word or a bare verb."""
    stripped = request.strip()
    if not stripped or stripped.endswith("?"):
        return not stripped
    tokens = normalize(stripped).split()
    if not tokens:
        return True
    if len(tokens) == 1 and tokens[0] not in _DOMAIN_TERMS:
        return True
    return tokens[-1] in _TRAILING_INCOMPLETE


def _is_domain_request(text: str) -> bool:
    """A question or command about the dataset's subject, even if STT clipped "Kognia"."""
    norm = normalize(text)
    tokens = set(norm.split())
    asks = "?" in text or norm.startswith(_REQUEST_STARTS)
    return asks and bool(tokens & _DOMAIN_TERMS)


def _is_backchannel(text: str) -> bool:
    tokens = normalize(text).split()
    return 0 < len(tokens) <= 2 and all(t in _BACKCHANNELS for t in tokens)
