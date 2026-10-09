"""Scores a manual shared-microphone session exported from the dashboard ("Exportar").

Reference file (JSON), what was actually said, in order:
    [{"person": "P1", "text": "Kognia, ¿cuántas IPS hay en Armenia?", "addressed": true},
     {"person": "P2", "text": "¿Vamos a almorzar después?", "addressed": false}, ...]

Usage: python bench/score_session.py export.json reference.json
Outputs WER, speaker attribution (best one-to-one label mapping), omitted interventions,
false activations, missed activations, ask-to-repeat count and latency p50/p95.
"""

import difflib
import itertools
import json
import sys
from pathlib import Path

from app.application.services.text_matching import normalize
from app.voice.latency_metrics import percentile
from bench.audio_bench import wer

MATCH_THRESHOLD = 0.45


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def main(export_path: Path, reference_path: Path) -> None:
    export = json.loads(export_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    segments = [s for s in export["segments"] if s["role"] == "user"]

    matches: list[tuple[dict, dict | None]] = []
    cursor = 0
    for ref in reference:
        best, best_score, best_index = None, 0.0, cursor
        for index in range(cursor, min(cursor + 6, len(segments))):
            score = similarity(ref["text"], segments[index]["text"])
            if score > best_score:
                best, best_score, best_index = segments[index], score, index
        if best is not None and best_score >= MATCH_THRESHOLD:
            matches.append((ref, best))
            cursor = best_index + 1
        else:
            matches.append((ref, None))

    persons = sorted({r["person"] for r in reference})
    labels = sorted(
        {
            s["speaker_label"]
            for _, s in matches
            if s and s["speaker_label"] != "Hablante desconocido"
        }
    )
    best_correct = 0
    for perm in itertools.permutations(persons, min(len(persons), len(labels))):
        mapping = dict(zip(labels, perm, strict=False))
        best_correct = max(
            best_correct,
            sum(
                1
                for r, s in matches
                if s and mapping.get(s["speaker_label"]) == r["person"]
            ),
        )
    matched = [m for m in matches if m[1] is not None]

    decisions = export.get("decisions", [])
    responded = [d for d in decisions if d["action"] == "respond"]
    asked = [d for d in decisions if d["action"] == "ask_repeat"]
    addressed_refs = [r for r in reference if r.get("addressed")]
    not_addressed_refs = [r for r in reference if r.get("addressed") is False]

    def answered(ref: dict) -> bool:
        return any(
            similarity(ref["text"], d["text"]) >= MATCH_THRESHOLD for d in responded
        )

    e2e = [
        t["stages_ms"]["e2e_latency"]
        for t in export.get("latency_turns", [])
        if "e2e_latency" in t["stages_ms"]
    ]
    first = [
        t["stages_ms"]["first_audio"]
        for t in export.get("latency_turns", [])
        if "first_audio" in t["stages_ms"]
    ]
    report = {
        "reference_interventions": len(reference),
        "omitted_interventions": sum(1 for _, s in matches if s is None),
        "wer": round(
            wer(
                [t for r in reference for t in normalize(r["text"]).split()],
                [t for s in segments for t in normalize(s["text"]).split()],
            ),
            3,
        ),
        "speaker_attribution_acc": round(best_correct / len(matched), 3)
        if matched
        else None,
        "unknown_speaker_segments": sum(
            1 for _, s in matched if s["speaker_label"] == "Hablante desconocido"
        ),
        "speakers_in_reference": len(persons),
        "speaker_labels_detected": len(labels),
        "false_activations": sum(1 for r in not_addressed_refs if answered(r)),
        "missed_activations": sum(1 for r in addressed_refs if not answered(r)),
        "ask_repeat": len(asked),
        "overlap_segments": sum(1 for s in segments if s.get("overlap_suspected")),
        "e2e_ms": {
            "p50": percentile(e2e, 50),
            "p95": percentile(e2e, 95),
            "n": len(e2e),
        },
        "first_audio_ms": {
            "p50": percentile(first, 50),
            "p95": percentile(first, 95),
            "n": len(first),
        },
        "browser_playback_ms_p50": percentile(
            export.get("browser_playback_ms", []), 50
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
