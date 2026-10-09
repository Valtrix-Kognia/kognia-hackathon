import difflib
import re
import unicodedata

_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalize(value: str) -> str:
    """Uppercase, strip accents and punctuation: 'Bogotá D.C' -> 'BOGOTA D C'."""
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = _NON_ALNUM.sub(" ", without_marks.upper())
    return _SPACES.sub(" ", cleaned).strip()


def best_matches(raw: str, candidates: list[str]) -> tuple[list[str], list[str]]:
    """Return (matches, suggestions) of canonical candidates for a user-provided value.

    Exact normalized match wins; otherwise prefix matches; otherwise close fuzzy matches.
    """
    target = normalize(raw)
    if not target:
        return [], []
    by_norm: dict[str, list[str]] = {}
    for candidate in candidates:
        by_norm.setdefault(normalize(candidate), []).append(candidate)

    if target in by_norm:
        return by_norm[target], []

    prefix = [
        c
        for norm, values in by_norm.items()
        if len(target) >= 4
        and (norm.startswith(target + " ") or target.startswith(norm + " "))
        for c in values
    ]
    if prefix:
        return prefix, []

    close = difflib.get_close_matches(target, list(by_norm), n=3, cutoff=0.84)
    if len(close) == 1:
        return by_norm[close[0]], []
    suggestions = [
        by_norm[n][0]
        for n in difflib.get_close_matches(target, list(by_norm), n=3, cutoff=0.6)
    ]
    return [], suggestions
