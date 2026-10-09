"""Dumps word-level STT output (speaker, timing, confidence) per scenario to design overlap cues."""

import asyncio
import json
import sys

import aiohttp
import numpy as np
from dotenv import load_dotenv

from bench.audio_bench import build_scenarios, enhance, mix, transcribe


async def main(names: list[str]) -> None:
    load_dotenv(".env.local")
    rng = np.random.default_rng(7)
    async with aiohttp.ClientSession() as session:
        for scenario in await build_scenarios(session):
            signal = mix(scenario, rng)
            if scenario.name.split("_")[0] not in names:
                continue
            pcm, _ = enhance(signal, "quail_l")
            finals = await transcribe(session, pcm)
            words = [
                {
                    "w": str(w),
                    "spk": w.speaker_id,
                    "t0": round(w.start_time, 2),
                    "t1": round(w.end_time, 2),
                    "conf": round(w.confidence, 3),
                }
                for f in finals
                for w in (f.words or [])
            ]
            audio_s = sum(u.end_s - u.start_s for u in scenario.utterances)
            span_s = max(u.end_s for u in scenario.utterances) - min(
                u.start_s for u in scenario.utterances
            )
            ref_words = sum(len(u.text.split()) for u in scenario.utterances)
            print(
                json.dumps(
                    {
                        "scenario": scenario.name,
                        "speech_s_sum": round(audio_s, 2),
                        "speech_span_s": round(span_s, 2),
                        "ref_words": ref_words,
                        "hyp_words": len(words),
                        "mean_conf": round(
                            float(np.mean([w["conf"] for w in words])), 3
                        )
                        if words
                        else None,
                        "min_conf": min((w["conf"] for w in words), default=None),
                        "words": words,
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1].split(",")))
