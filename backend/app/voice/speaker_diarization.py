from dataclasses import dataclass, field
from typing import Protocol

UNKNOWN_SPEAKER = None


class TimedWord(Protocol):
    @property
    def start_time(self) -> float: ...

    @property
    def end_time(self) -> float: ...

    @property
    def confidence(self) -> float: ...

    @property
    def speaker_id(self) -> str | None: ...

    def __str__(self) -> str: ...


class SpeechAlternative(Protocol):
    text: str
    start_time: float
    end_time: float
    confidence: float
    speaker_id: str | None
    words: list | None


@dataclass
class SpeakerSpan:
    """Consecutive words attributed to one provider speaker id (None = not attributable)."""

    speaker_id: str | None
    words: list[str] = field(default_factory=list)
    start_s: float = 0.0
    end_s: float = 0.0
    confidences: list[float] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.words)

    @property
    def mean_confidence(self) -> float:
        return (
            sum(self.confidences) / len(self.confidences) if self.confidences else 0.0
        )


@dataclass
class DiarizedUtterance:
    text: str
    spans: list[SpeakerSpan]
    start_s: float
    end_s: float
    mean_confidence: float
    speaker_switches: int
    overlap_suspected: bool
    low_confidence: bool

    @property
    def speakers(self) -> set[str]:
        return {s.speaker_id for s in self.spans if s.speaker_id is not None}

    @property
    def multi_speaker(self) -> bool:
        substantial = {
            s.speaker_id
            for s in self.spans
            if s.speaker_id is not None and len(s.words) >= MIN_SUBSTANTIAL_WORDS
        }
        return len(substantial) >= 2


MIN_SUBSTANTIAL_WORDS = 3
FLICKER_MAX_WORDS = 1
RAPID_SWITCHES = 3
LOW_CONFIDENCE = 0.55


class SpeakerDiarizationService:
    """Splits one final STT result into per-speaker spans using word-level speaker ids.

    It never invents a speaker: words without an id, and single-word "flickers" between two
    spans of the same speaker (typical diarization noise in overlapped or short audio), are
    marked as not attributable instead of being assigned to someone.
    """

    def analyze(self, alternative: SpeechAlternative) -> DiarizedUtterance:
        words = list(alternative.words or [])
        if not words:
            span = SpeakerSpan(
                speaker_id=_clean(alternative.speaker_id),
                words=alternative.text.split(),
                start_s=alternative.start_time,
                end_s=alternative.end_time,
                confidences=[alternative.confidence] if alternative.confidence else [],
            )
            return self._summarize(alternative.text, [span] if span.words else [])

        spans: list[SpeakerSpan] = []
        for word in words:
            token = str(word).strip()
            if not token:
                continue
            speaker = _clean(word.speaker_id)
            if spans and spans[-1].speaker_id == speaker:
                current = spans[-1]
            else:
                current = SpeakerSpan(speaker_id=speaker, start_s=word.start_time)
                spans.append(current)
            current.words.append(token)
            current.end_s = word.end_time
            current.confidences.append(word.confidence)
        switches = max(0, len(spans) - 1)
        return self._summarize(alternative.text, self._mark_flickers(spans), switches)

    @staticmethod
    def _mark_flickers(spans: list[SpeakerSpan]) -> list[SpeakerSpan]:
        for index in range(1, len(spans) - 1):
            span = spans[index]
            neighbours_match = (
                spans[index - 1].speaker_id == spans[index + 1].speaker_id
            )
            if len(span.words) <= FLICKER_MAX_WORDS and neighbours_match:
                span.speaker_id = UNKNOWN_SPEAKER
        merged: list[SpeakerSpan] = []
        for span in spans:
            if merged and merged[-1].speaker_id == span.speaker_id:
                merged[-1].words.extend(span.words)
                merged[-1].confidences.extend(span.confidences)
                merged[-1].end_s = span.end_s
            else:
                merged.append(span)
        return merged

    @staticmethod
    def _summarize(
        text: str, spans: list[SpeakerSpan], raw_switches: int = 0
    ) -> DiarizedUtterance:
        confidences = [c for s in spans for c in s.confidences]
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        short_spans = sum(1 for s in spans if len(s.words) < MIN_SUBSTANTIAL_WORDS)
        overlap = raw_switches >= RAPID_SWITCHES or (
            len({s.speaker_id for s in spans if s.speaker_id}) >= 2 and short_spans >= 2
        )
        return DiarizedUtterance(
            text=text.strip(),
            spans=spans,
            start_s=spans[0].start_s if spans else 0.0,
            end_s=spans[-1].end_s if spans else 0.0,
            mean_confidence=mean_conf,
            speaker_switches=raw_switches,
            overlap_suspected=overlap,
            low_confidence=bool(confidences) and mean_conf < LOW_CONFIDENCE,
        )


def _clean(speaker_id: object) -> str | None:
    if speaker_id is None:
        return None
    value = str(speaker_id).strip()
    return value or None
