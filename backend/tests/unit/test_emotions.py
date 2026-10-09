import asyncio
from datetime import UTC, datetime

from app.domain.models.transcript_segment import TranscriptSegment
from app.emotions.emotion_analyzer import EmotionAnalyzer
from app.emotions.emotion_worker import EmotionWorker
from app.emotions.text_classifier import RawPrediction


class StubClassifier:
    model_name = "stub"

    def __init__(self, prediction: RawPrediction | Exception) -> None:
        self._prediction = prediction
        self.calls = 0

    def predict(self, text: str) -> RawPrediction:
        self.calls += 1
        if isinstance(self._prediction, Exception):
            raise self._prediction
        return self._prediction


def segment(text: str, is_final: bool = True) -> TranscriptSegment:
    return TranscriptSegment(
        id="u-1",
        session_id="room",
        role="user",
        speaker_id="0",
        speaker_label="Hablante 1",
        text=text,
        start_ms=0,
        end_ms=10,
        is_final=is_final,
        timestamp=datetime.now(UTC),
    )


PREDICTION = RawPrediction(
    sentiment="NEG",
    sentiment_probas={"NEG": 0.9, "NEU": 0.08, "POS": 0.02},
    emotion="fear",
    emotion_probas={"fear": 0.55, "others": 0.4, "joy": 0.05},
)


def test_maps_labels_and_uses_model_scores() -> None:
    result = EmotionAnalyzer(StubClassifier(PREDICTION)).analyze(
        segment("me da miedo que cierren el hospital")
    )
    assert result.status == "ok"
    assert (result.sentiment, result.sentiment_score) == ("negativo", 0.9)
    assert (result.emotion, result.emotion_score) == ("miedo", 0.55)
    assert result.low_confidence is True
    assert result.source == "texto"


def test_short_text_is_not_classified() -> None:
    stub = StubClassifier(PREDICTION)
    result = EmotionAnalyzer(stub).analyze(segment("sí claro"))
    assert result.status == "texto_insuficiente"
    assert result.sentiment is None and result.emotion_score is None
    assert stub.calls == 0


def test_classifier_failure_reports_error_without_scores() -> None:
    result = EmotionAnalyzer(StubClassifier(RuntimeError("boom"))).analyze(
        segment("una frase suficientemente larga")
    )
    assert result.status == "error"
    assert result.sentiment is None


async def test_worker_ignores_partials_and_delivers_results() -> None:
    results = []
    analyzer = EmotionAnalyzer(StubClassifier(PREDICTION))
    worker = EmotionWorker(lambda: analyzer, results.append)
    worker.start()
    worker.submit(segment("parcial que no se analiza", is_final=False))
    worker.submit(segment("frase final para analizar"))
    for _ in range(50):
        if results:
            break
        await asyncio.sleep(0.01)
    await worker.aclose()
    assert len(results) == 1
    assert results[0].segment_id == "u-1"
