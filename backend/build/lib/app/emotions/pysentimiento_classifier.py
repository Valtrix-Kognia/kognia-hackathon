import threading

from app.emotions.text_classifier import RawPrediction


class PysentimientoClassifier:
    """Spanish RoBERTuito sentiment + emotion models (pysentimiento). CPU, thread-safe."""

    model_name = "pysentimiento/robertuito-{sentiment,emotion}-analysis"

    def __init__(self) -> None:
        from pysentimiento import create_analyzer

        self._sentiment = create_analyzer(task="sentiment", lang="es")
        self._emotion = create_analyzer(task="emotion", lang="es")
        self._lock = threading.Lock()

    def predict(self, text: str) -> RawPrediction:
        with self._lock:
            sentiment = self._sentiment.predict(text)
            emotion = self._emotion.predict(text)
        return RawPrediction(
            sentiment=sentiment.output,
            sentiment_probas=dict(sentiment.probas),
            emotion=emotion.output,
            emotion_probas=dict(emotion.probas),
        )
