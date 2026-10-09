"""Runs a fixed spoken-question set through `lk agent debugger --audio` and summarizes latency.

Usage (with an audio debugger session already started):
    python bench/latency_run.py --log <agent log path> --label baseline
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from app.voice.latency_metrics import percentile

QUESTIONS = [
    "¿Cuántas IPS hay en el Quindío?",
    "¿Qué departamentos tienen más prestadores?",
    "¿Cuántas sedes públicas hay en Antioquia?",
    "¿Qué niveles de atención aparecen en los datos?",
    "¿Cuántas camas hay en Risaralda?",
    "¿Qué especialidades ofrece el hospital San Juan de Dios?",
    "Busca la clínica Avidanti en Manizales.",
    "Gracias, eso es todo.",
]

LATENCY_LINE = re.compile(r"turn latency (\{.*)")


def run_turn(lk: str, question: str) -> dict:
    proc = subprocess.run(
        [
            lk,
            "agent",
            "debugger",
            "say",
            "--metrics",
            "--json",
            "--timeout",
            "90s",
            question,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "question": question,
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:],
    }


def read_latencies(log_path: Path, offset: int) -> list[dict]:
    with log_path.open(encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        decoder = json.JSONDecoder()
        return [
            decoder.raw_decode(m.group(1))[0]
            for line in fh
            if (m := LATENCY_LINE.search(line))
        ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--lk", default=os.environ.get("LK_BIN", "lk"))
    parser.add_argument("--out", type=Path, default=Path("bench/results"))
    parser.add_argument("--parse-only", action="store_true")
    args = parser.parse_args()

    offset = 0 if args.parse_only else args.log.stat().st_size
    turns = [] if args.parse_only else [run_turn(args.lk, q) for q in QUESTIONS]
    latencies = read_latencies(args.log, offset)

    def stage(key: str) -> list[float]:
        return [t["stages_ms"][key] for t in latencies if key in t["stages_ms"]]

    summary = {
        "label": args.label,
        "turns_sent": len(QUESTIONS),
        "turns_measured": len(latencies),
        "failed_turns": [t["question"] for t in turns if t["exit_code"] != 0],
    }
    for key in (
        "first_audio",
        "e2e_latency",
        "end_of_turn_delay",
        "transcription_delay",
        "llm_node_ttft",
        "tts_node_ttfb",
    ):
        values = stage(key)
        summary[key] = {
            "n": len(values),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
        }
    socrata = [t["socrata_ms"] for t in latencies if t["tools"]]
    summary["socrata_ms"] = {
        "n": len(socrata),
        "p50": percentile(socrata, 50),
        "p95": percentile(socrata, 95),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"latency_{args.label}.json"
    out_file.write_text(
        json.dumps(
            {"summary": summary, "turns": latencies, "raw": turns},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
