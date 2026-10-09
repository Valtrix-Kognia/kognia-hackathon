import difflib
import re
from dataclasses import dataclass
from enum import StrEnum

from app.application.services.text_matching import normalize

WAKE_KEY = "KOGNIA"
CONFIRMED_SPELLINGS = {"KOGNIA", "COGNIA"}
MIN_FUZZY_LENGTH = 5
DEFAULT_VARIANTS = ("CUCNIA", "COCNEA", "CONIA", "KONIA", "COGNA", "KOGNA", "CONYA")
PROBABLE_RATIO = 0.8
AMBIGUOUS_RATIO = 0.67
MAX_POSITION = 3
_LEADING_FILLERS = {"OYE", "HOLA", "EY", "EH", "BUENO", "A", "VER", "PREGUNTA", "OIGA"}


class WakeLevel(StrEnum):
    CONFIRMED = "confirmada"
    PROBABLE = "probable"
    AMBIGUOUS = "ambigua"
    NONE = "ninguna"


@dataclass(frozen=True)
class WakeWordMatch:
    level: WakeLevel
    request: str
    matched_token: str | None = None

    @property
    def found(self) -> bool:
        return self.level in (WakeLevel.CONFIRMED, WakeLevel.PROBABLE)


def phonetic_key(token: str) -> str:
    """Collapse Spanish spellings STT produces for "Kognia": C/K/Q, CN/KN→GN, EA→IA."""
    key = normalize(token).replace(" ", "")
    key = key.replace("QU", "K")
    key = re.sub(r"C(?=[EI])", "S", key)
    key = key.replace("C", "K")
    key = re.sub(r"[KG]N", "GN", key)
    return key.replace("EA", "IA")


class WakeWordDetector:
    """Textual activation detector over STT output, with bounded fuzzy matching.

    It is not acoustic keyword spotting. Only tokens near the start of the utterance
    can confirm an activation; a similar word later in the sentence is at most ambiguous.
    """

    def __init__(self, variants: tuple[str, ...] = DEFAULT_VARIANTS) -> None:
        self._variant_keys = {phonetic_key(v) for v in variants}

    def detect(self, text: str) -> WakeWordMatch:
        tokens = text.split()
        best = WakeWordMatch(WakeLevel.NONE, text.strip())
        position = 0
        for index, token in enumerate(tokens):
            norm = normalize(token)
            if not norm:
                continue
            level = self._classify(norm.replace(" ", ""), phonetic_key(token))
            near_start = position < MAX_POSITION
            if norm not in _LEADING_FILLERS:
                position += 1
            if level is WakeLevel.NONE:
                continue
            if not near_start:
                level = WakeLevel.AMBIGUOUS
            if level is not WakeLevel.AMBIGUOUS:
                request = " ".join(tokens[index + 1 :]).lstrip(",.:; ").strip()
                return WakeWordMatch(level, request, token)
            if best.level is WakeLevel.NONE:
                best = WakeWordMatch(WakeLevel.AMBIGUOUS, text.strip(), token)
        return best

    def _classify(self, spelling: str, key: str) -> WakeLevel:
        if spelling in CONFIRMED_SPELLINGS:
            return WakeLevel.CONFIRMED
        if key == WAKE_KEY or key in self._variant_keys:
            return WakeLevel.PROBABLE
        if not MIN_FUZZY_LENGTH <= len(key) <= 9:
            return WakeLevel.NONE
        ratio = difflib.SequenceMatcher(None, key, WAKE_KEY).ratio()
        if ratio >= PROBABLE_RATIO:
            return WakeLevel.PROBABLE
        if ratio >= AMBIGUOUS_RATIO:
            return WakeLevel.AMBIGUOUS
        return WakeLevel.NONE


_DEFAULT = WakeWordDetector()


def find_wake_word(text: str) -> WakeWordMatch:
    return _DEFAULT.detect(text)
