import difflib

from app.application.services.text_matching import normalize
from app.voice.speaker_diarization import DiarizedUtterance


def align_to_committed(
    utterances: list[DiarizedUtterance], committed_text: str
) -> tuple[list[DiarizedUtterance], list[DiarizedUtterance]]:
    """Split buffered STT finals into (part of the committed turn, stale leftovers).

    LiveKit commits a turn from the finals it accepted; finals heard while it skipped a
    turn (e.g. during uninterruptible speech) must not leak into the next decision.
    The committed turn is the suffix of the buffer whose text best matches what LiveKit
    committed.
    """
    target = normalize(committed_text)
    if not utterances or not target:
        return utterances, []
    best_start, best_ratio = len(utterances) - 1, -1.0
    for start in range(len(utterances) - 1, -1, -1):
        candidate = normalize(" ".join(u.text for u in utterances[start:]))
        ratio = difflib.SequenceMatcher(None, candidate, target).ratio()
        if ratio > best_ratio + 1e-9:
            best_start, best_ratio = start, ratio
    return utterances[best_start:], utterances[:best_start]
