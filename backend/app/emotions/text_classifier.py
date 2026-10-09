from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawPrediction:
    sentiment: str
    sentiment_probas: dict[str, float]
    emotion: str
    emotion_probas: dict[str, float]


class TextClassifier(Protocol):
    model_name: str

    def predict(self, text: str) -> RawPrediction: ...
