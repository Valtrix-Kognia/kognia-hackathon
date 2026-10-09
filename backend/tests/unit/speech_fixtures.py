from dataclasses import dataclass, field


@dataclass
class FakeWord:
    text: str
    start_time: float
    end_time: float
    speaker_id: str | None
    confidence: float = 0.95

    def __str__(self) -> str:
        return self.text


@dataclass
class FakeAlternative:
    text: str
    words: list[FakeWord] | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    confidence: float = 0.9
    speaker_id: str | None = None
    language: str = "es"
    extra: dict = field(default_factory=dict)


def alt(
    *chunks: tuple[str | None, str], confidence: float = 0.95, t0: float = 0.0
) -> FakeAlternative:
    """Build an alternative from (speaker_id, text) chunks, 0.3 s per word."""
    words: list[FakeWord] = []
    t = t0
    for speaker, text in chunks:
        for token in text.split():
            words.append(FakeWord(token, t, t + 0.25, speaker, confidence))
            t += 0.3
    return FakeAlternative(
        text=" ".join(w.text for w in words),
        words=words,
        start_time=t0,
        end_time=t,
        speaker_id=words[0].speaker_id if words else None,
    )
