import logging
from datetime import UTC, datetime

from app.domain.models.emotion_analysis import EmotionAnalysis
from app.domain.models.transcript_segment import TranscriptSegment
from app.emotions.text_classifier import TextClassifier

logger = logging.getLogger("kognia.emotions")

MIN_WORDS = 3
LOW_CONFIDENCE_THRESHOLD = 0.6

_SENTIMENT_MAP = {"POS": "positivo", "NEU": "neutral", "NEG": "negativo"}
_EMOTION_MAP = {
    "joy": "alegria",
    "sadness": "tristeza",
    "anger": "enojo",
    "fear": "miedo",
    "surprise": "sorpresa",
    "disgust": "asco",
    "others": "neutral",
}


class EmotionAnalyzer:
    """Maps classifier output to the public contract; never invents scores."""

    def __init__(self, classifier: TextClassifier) -> None:
        self._classifier = classifier

    def analyze(self, segment: TranscriptSegment) -> EmotionAnalysis:
        base = {
            "segment_id": segment.id,
            "session_id": segment.session_id,
            "speaker_label": segment.speaker_label,
            "model": self._classifier.model_name,
            "analyzed_at": datetime.now(UTC),
        }
        if len(segment.text.split()) < MIN_WORDS:
            return EmotionAnalysis(status="texto_insuficiente", **base)
        try:
            raw = self._classifier.predict(segment.text)
        except Exception:
            logger.exception("emotion classifier failed")
            return EmotionAnalysis(status="error", **base)
        sentiment_score = raw.sentiment_probas.get(raw.sentiment)
        emotion_score = raw.emotion_probas.get(raw.emotion)
        scores = [s for s in (sentiment_score, emotion_score) if s is not None]
        return EmotionAnalysis(
            status="ok",
            sentiment=_SENTIMENT_MAP.get(raw.sentiment, "neutral"),
            sentiment_score=round(sentiment_score, 3)
            if sentiment_score is not None
            else None,
            emotion=_EMOTION_MAP.get(raw.emotion, "neutral"),
            emotion_score=round(emotion_score, 3)
            if emotion_score is not None
            else None,
            low_confidence=bool(scores) and min(scores) < LOW_CONFIDENCE_THRESHOLD,
            **base,
        )
