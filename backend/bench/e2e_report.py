"""Per-turn and per-category report of a browser e2e session (export + reference).

Joins backend traces (metrics.turn) and browser playback measurements by turn_id, and
compares the decision taken for each reference intervention with the expected one.
Usage: python -m bench.e2e_report export.json reference.json
"""

import difflib
import json
import sys
from collections import defaultdict
from pathlib import Path

from app.application.services.text_matching import normalize
from app.voice.latency_metrics import percentile


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def main(export_path: Path, reference_path: Path) -> dict:
    export = json.loads(export_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    decisions = export.get("decisions", [])
    traces = {
        t["turn_id"]: t for t in export.get("latency_turns", []) if t.get("turn_id")
    }
    playback = {p["turn_id"]: p for p in export.get("browser_playback", [])}

    rows = []
    for ref in reference:
        best, score = None, 0.0
        for decision in decisions:
            candidates = [decision.get("text", ""), *decision.get("merged_from", [])]
            s = (
                max(similarity(ref["text"], c) for c in candidates if c)
                if any(candidates)
                else 0
            )
            if s > score:
                best, score = decision, s
        matched = best if score >= 0.45 else None
        trace = traces.get(matched["turn_id"]) if matched else None
        browser = playback.get(matched["turn_id"]) if matched else None
        stages = (trace or {}).get("stages_ms", {})
        rows.append(
            {
                "category": ref.get("category"),
                "person": ref["person"],
                "text": ref["text"],
                "expected": ref.get("expected"),
                "turn_id": matched["turn_id"] if matched else None,
                "action": matched["action"] if matched else "sin_decision",
                "reason": matched["reason"] if matched else None,
                "activation": matched.get("activation") if matched else None,
                "first_audio_ms": stages.get("first_audio"),
                "eou_ms": stages.get("end_of_turn_delay"),
                "llm_ttft_ms": stages.get("llm_node_ttft"),
                "tts_ttfb_ms": stages.get("tts_node_ttfb"),
                "socrata_http_ms": (trace or {}).get("socrata_http_ms"),
                "tools": [t["tool"] for t in (trace or {}).get("tools", [])],
                "browser": browser,
            }
        )

    def ok(row: dict) -> bool:
        expected = row["expected"] or ""
        if expected == "ask_repeat_or_respond":
            return row["action"] in ("ask_repeat", "respond", "hold")
        if expected == "respond":
            return row["action"] in ("respond", "hold", "listen")
        return row["action"] == expected

    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(row)

    def stats(values: list[float]) -> dict:
        values = [v for v in values if isinstance(v, int | float)]
        return {
            "n": len(values),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
        }

    measured_browser = [
        p["decision_to_audible_ms"]
        for p in playback.values()
        if p.get("status") == "medido"
    ]
    report = {
        "interventions": len(rows),
        "decision_matches_expected": f"{sum(ok(r) for r in rows)}/{len(rows)}",
        "failed": [
            {
                k: r[k]
                for k in (
                    "category",
                    "text",
                    "expected",
                    "action",
                    "reason",
                    "activation",
                )
            }
            for r in rows
            if not ok(r)
        ],
        "first_audio_ms": stats([r["first_audio_ms"] for r in rows]),
        "end_of_turn_ms": stats([r["eou_ms"] for r in rows]),
        "llm_ttft_ms": stats([r["llm_ttft_ms"] for r in rows]),
        "tts_ttfb_ms": stats([r["tts_ttfb_ms"] for r in rows]),
        "socrata_http_ms": stats([r["socrata_http_ms"] for r in rows if r["tools"]]),
        "browser_decision_to_audible_ms": stats(measured_browser),
        "browser_superseded": sum(
            1 for p in playback.values() if p.get("status") == "reemplazado"
        ),
        "by_category": {
            cat: {
                "ok": f"{sum(ok(r) for r in items)}/{len(items)}",
                "first_audio_p50": stats([r["first_audio_ms"] for r in items])["p50"],
            }
            for cat, items in by_category.items()
        },
        "rows": rows,
    }
    return report


if __name__ == "__main__":
    result = main(Path(sys.argv[1]), Path(sys.argv[2]))
    out = Path(sys.argv[1]).with_suffix(".report.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    printable = {k: v for k, v in result.items() if k != "rows"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
