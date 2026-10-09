from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Sentiment = Literal["positivo", "neutral", "negativo"]
Emotion = Literal[
    "alegria", "tristeza", "enojo", "miedo", "sorpresa", "asco", "neutral"
]
AnalysisStatus = Literal["ok", "texto_insuficiente", "error"]


class EmotionAnalysis(BaseModel):
    """Text-only estimate for one consolidated transcript segment."""

    segment_id: str
    session_id: str
    speaker_label: str
    status: AnalysisStatus
    sentiment: Sentiment | None = None
    sentiment_score: float | None = None
    emotion: Emotion | None = None
    emotion_score: float | None = None
    low_confidence: bool = False
    model: str
    source: Literal["texto"] = "texto"
    analyzed_at: datetime
