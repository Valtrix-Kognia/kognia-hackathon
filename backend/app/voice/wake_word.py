import difflib
from dataclasses import dataclass

from app.application.services.text_matching import normalize

WAKE_WORD = "KOGNIA"
_KNOWN_VARIANTS = {
    "KOGNIA",
    "COGNIA",
    "KONIA",
    "CONIA",
    "KOGNA",
    "KONYA",
    "COGNIAS",
}
_MIN_RATIO = 0.8


@dataclass(frozen=True)
class WakeWordMatch:
    found: bool
    request: str
    matched_token: str | None = None


def find_wake_word(text: str) -> WakeWordMatch:
    """Textual match of "Kognia" in a transcript, tolerant to common STT spellings.

    This is not acoustic keyword spotting: it works on what the STT already transcribed.
    """
    original_tokens = text.split()
    for index, token in enumerate(original_tokens):
        norm = normalize(token)
        if not norm:
            continue
        if norm in _KNOWN_VARIANTS or (
            4 <= len(norm) <= 8
            and difflib.SequenceMatcher(None, norm, WAKE_WORD).ratio() >= _MIN_RATIO
        ):
            request = " ".join(original_tokens[index + 1 :]).lstrip(",.:; ").strip()
            return WakeWordMatch(True, request, token)
    return WakeWordMatch(False, text.strip())
