"""Time to first audio byte of Cartesia models through LiveKit Inference, streaming input.

Variants are interleaved per round. Usage: python -m bench.tts_ttfb --n 8
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import aiohttp
import numpy as np
from dotenv import load_dotenv
from livekit.agents import inference

from app.voice.latency_metrics import percentile

VOICE = "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c"
SENTENCES = [
    "En Caldas hay ciento noventa y tres prestadores únicos y doscientas once sedes.",
    "Un momento, consulto los datos oficiales.",
    "Los departamentos con más prestadores son Bogotá, Antioquia y Santander.",
]


async def first_audio_ms(tts: inference.TTS, text: str) -> tuple[float, float]:
    """(ms to first audio frame, ms of leading silence inside the audio)."""
    started = time.perf_counter()
    first: float | None = None
    audio_ms = 0.0
    async with tts.stream() as stream:
        stream.push_text(text)
        stream.end_input()
        async for event in stream:
            if first is None:
                first = (time.perf_counter() - started) * 1000
            samples = (
                np.frombuffer(event.frame.data, dtype=np.int16).astype(np.float32)
                / 32768
            )
            if np.sqrt(np.mean(samples**2)) >= 0.012:
                return first, audio_ms
            audio_ms += event.frame.duration * 1000
    return first or float("nan"), audio_ms


async def main() -> None:
    load_dotenv(".env.local")
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=8)
    args = parser.parse_args()
    async with aiohttp.ClientSession() as session:
        variants = {
            model: inference.TTS(
                model=model, voice=VOICE, language="es", http_session=session
            )
            for model in (
                "cartesia/sonic-3",
                "cartesia/sonic-turbo",
                "cartesia/sonic-3.5",
            )
        }
        results: dict[str, list[float]] = {k: [] for k in variants}
        silence: dict[str, list[float]] = {k: [] for k in variants}
        for round_index in range(args.n):
            text = SENTENCES[round_index % len(SENTENCES)]
            for name, tts in variants.items():
                try:
                    first, lead = await first_audio_ms(tts, text)
                    results[name].append(round(first, 1))
                    silence[name].append(round(lead, 1))
                except Exception as exc:
                    results[name].append(float("nan"))
                    print(f"{name} falló: {exc!r}")
    summary = {
        name: {
            "n_ok": sum(1 for v in values if v == v),
            "ttfb_p50_ms": percentile([v for v in values if v == v], 50),
            "ttfb_p95_ms": percentile([v for v in values if v == v], 95),
            "leading_silence_p50_ms": percentile(silence[name], 50),
        }
        for name, values in results.items()
    }
    Path("bench/results/tts_ttfb.json").write_text(
        json.dumps({"summary": summary, "samples": results}, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
