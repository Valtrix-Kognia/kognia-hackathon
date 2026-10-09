"""Compares e2e runs from their exports: decisions, per-turn latency and browser playback.
Usage: python -m bench.e2e_compare v1 v2 v3   (reads bench/results/e2e/sesion_*_<label>.json)
"""

import json
import sys
from pathlib import Path

from app.voice.latency_metrics import percentile

ROOT = Path("bench/results/e2e")


def stats(values: list[float]) -> str:
    values = [v for v in values if isinstance(v, int | float)]
    if not values:
        return "—"
    return (
        f"{percentile(values, 50):.0f} / {percentile(values, 95):.0f} (n={len(values)})"
    )


def summarize(label: str) -> dict:
    exports = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(ROOT.glob(f"sesion_*_{label}.json"))
    ]
    turns = [
        t
        for e in exports
        for t in e.get("latency_turns", [])
        if t.get("outcome") == "respondido"
    ]
    decisions = [d for e in exports for d in e.get("decisions", [])]
    playback = [p for e in exports for p in e.get("browser_playback", [])]
    tools = [x for t in turns for x in t.get("tools", [])]

    def stage(key: str) -> list[float]:
        return [t["stages_ms"][key] for t in turns if key in t["stages_ms"]]

    counts: dict[str, int] = {}
    for d in decisions:
        counts[f"{d['action']}:{d['reason']}"] = (
            counts.get(f"{d['action']}:{d['reason']}", 0) + 1
        )
    return {
        "sesiones": len(exports),
        "turnos_respondidos": len(turns),
        "primer_audio_ms": stats(stage("first_audio")),
        "fin_de_turno_ms": stats(stage("end_of_turn_delay")),
        "llm_ttft_ms": stats(stage("llm_node_ttft")),
        "tts_ttfb_ms": stats(stage("tts_node_ttfb")),
        "socrata_http_ms": stats([x["http_ms"] for x in tools if "http_ms" in x]),
        "navegador_decision_a_audio_ms": stats(
            [
                p["decision_to_audible_ms"]
                for p in playback
                if p.get("status") == "medido"
            ]
        ),
        "navegador_reemplazados": sum(
            1 for p in playback if p.get("status") == "reemplazado"
        ),
        "decisiones": dict(sorted(counts.items())),
    }


if __name__ == "__main__":
    report = {label: summarize(label) for label in sys.argv[1:]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
