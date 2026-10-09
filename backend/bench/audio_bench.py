"""Offline shared-microphone benchmark: noise suppression x diarization x overlap handling.

Builds single-channel scenarios from distinct synthetic Spanish voices (LiveKit Inference TTS),
optionally adds non-speech noise, runs each through an ai-coustics configuration and the
same STT used in production (Deepgram nova-3, es, diarize), then scores:
  - WER against the known script,
  - speaker attribution accuracy (best one-to-one mapping of provider ids to true speakers),
  - speakers detected vs speakers present,
  - overlap flags raised by SpeakerDiarizationService.

Synthetic voices are cleaner and more distinct than people in a real room, so these numbers
are an upper bound for diarization quality, not a substitute for the manual protocol.

Usage: python bench/audio_bench.py [--conditions none,quail_vf_s,quail_l] [--scenarios ...]
"""

import argparse
import asyncio
import hashlib
import itertools
import json
import os
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import numpy as np
from dotenv import load_dotenv
from livekit import api, rtc
from livekit.agents import inference, stt
from livekit.plugins import ai_coustics

from app.application.services.text_matching import normalize
from app.voice.speaker_diarization import SpeakerDiarizationService
from app.voice.worker import BASE_KEYTERMS

SR = 48_000
FRAME = 480
CACHE = Path("bench/audio_cache")
OUT = Path("bench/results")

VOICES = {
    "A": ("cartesia/sonic-3", "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c"),
    "B": ("inworld/inworld-tts-1", "Diego"),
    "C": ("deepgram/aura-2", "celeste"),
    "D": ("deepgram/aura-2", "nestor"),
}

LINES = {
    "A": [
        "Kognia, ¿cuántas IPS hay en el Quindío?",
        "¿Y cuántas de esas son públicas?",
    ],
    "B": [
        "Yo quisiera saber qué departamentos tienen más prestadores.",
        "Muy bien, gracias.",
    ],
    "C": ["Kognia, busca hospitales en Armenia.", "¿Cuántas camas hay en Risaralda?"],
    "D": [
        "Necesito la información de capacidad instalada en Caldas.",
        "Perfecto, eso me sirve.",
    ],
}


BENCH_KEYTERMS = [
    *BASE_KEYTERMS,
    "Quindío",
    "Risaralda",
    "Caldas",
    "Armenia",
    "Antioquia",
    "Bogotá D.C",
]


@dataclass
class Utterance:
    speaker: str
    text: str
    start_s: float
    audio: np.ndarray

    @property
    def end_s(self) -> float:
        return self.start_s + len(self.audio) / SR


@dataclass
class Scenario:
    name: str
    utterances: list[Utterance]
    noise: str | None
    snr_db: float
    overlap: bool


async def synthesize(
    session: aiohttp.ClientSession, speaker: str, text: str
) -> np.ndarray:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{speaker}_{hashlib.sha1(text.encode()).hexdigest()[:10]}.npy"
    if path.exists():
        return np.load(path)
    model, voice = VOICES[speaker]
    tts = inference.TTS(
        model=model, voice=voice, language="es", sample_rate=SR, http_session=session
    )
    frames = []
    async with tts.synthesize(text) as stream:
        async for chunk in stream:
            frames.append(np.frombuffer(chunk.frame.data, dtype=np.int16))
    audio = np.concatenate(frames).astype(np.float32) / 32768.0
    np.save(path, audio)
    return audio


def noise(kind: str, n: int, rng: np.random.Generator) -> np.ndarray:
    if kind == "fan":
        white = rng.standard_normal(n)
        brown = np.cumsum(white)
        brown -= np.convolve(brown, np.ones(4800) / 4800, mode="same")
        return brown / (np.abs(brown).max() + 1e-9)
    if kind == "music":
        t = np.arange(n) / SR
        notes = [220.0, 277.18, 329.63, 440.0, 369.99, 293.66]
        signal = np.zeros(n)
        for i, f in enumerate(notes):
            envelope = (np.sin(2 * np.pi * (0.5 + i * 0.13) * t) > 0).astype(float)
            signal += envelope * np.sin(2 * np.pi * f * t) * 0.3
        return signal / (np.abs(signal).max() + 1e-9)
    raise ValueError(kind)


def mix(scenario: Scenario, rng: np.random.Generator) -> np.ndarray:
    total = int((max(u.end_s for u in scenario.utterances) + 1.5) * SR)
    speech = np.zeros(total, dtype=np.float32)
    for u in scenario.utterances:
        start = int(u.start_s * SR)
        speech[start : start + len(u.audio)] += u.audio
    if scenario.noise:
        n = noise(scenario.noise, total, rng).astype(np.float32)
        speech_power = np.mean(speech[np.abs(speech) > 1e-3] ** 2)
        noise_power = np.mean(n**2) + 1e-12
        n *= np.sqrt(speech_power / (noise_power * 10 ** (scenario.snr_db / 10)))
        speech = speech + n
    peak = np.abs(speech).max()
    return speech / peak * 0.9 if peak > 0.9 else speech


async def build_scenarios(session: aiohttp.ClientSession) -> list[Scenario]:
    audio: dict[tuple[str, int], np.ndarray] = {}
    for speaker, lines in LINES.items():
        for i, line in enumerate(lines):
            audio[(speaker, i)] = await synthesize(session, speaker, line)

    def turns(order: list[tuple[str, int]], gap: float = 0.8) -> list[Utterance]:
        t, out = 0.5, []
        for speaker, i in order:
            out.append(Utterance(speaker, LINES[speaker][i], t, audio[(speaker, i)]))
            t = out[-1].end_s + gap
        return out

    def overlapped(order: list[tuple[str, int]], fraction: float) -> list[Utterance]:
        t, out = 0.5, []
        for speaker, i in order:
            out.append(Utterance(speaker, LINES[speaker][i], t, audio[(speaker, i)]))
            t = out[-1].start_s + (out[-1].end_s - out[-1].start_s) * fraction
        return out

    return [
        Scenario("1_una_persona_silencio", turns([("A", 0)]), None, 0, False),
        Scenario("2_una_persona_ventilador", turns([("A", 0)]), "fan", 5, False),
        Scenario("3_una_persona_musica", turns([("A", 0)]), "music", 5, False),
        Scenario("4_dos_personas_turnos", turns([("A", 0), ("B", 0)]), None, 0, False),
        Scenario(
            "5_tres_personas_turnos",
            turns([("A", 0), ("B", 0), ("C", 0)]),
            "fan",
            15,
            False,
        ),
        Scenario(
            "6_cuatro_personas_turnos",
            turns([("A", 0), ("B", 0), ("C", 0), ("D", 0)]),
            "fan",
            15,
            False,
        ),
        Scenario(
            "7_dos_simultaneas", overlapped([("A", 0), ("B", 0)], 0.4), None, 0, True
        ),
        Scenario(
            "8_tres_simultaneas",
            overlapped([("A", 0), ("B", 0), ("C", 0)], 0.4),
            None,
            0,
            True,
        ),
    ]


def make_enhancer(condition: str) -> rtc.FrameProcessor[rtc.AudioFrame] | None:
    if condition == "none":
        return None
    model, level = {
        "quail_vf_s": (ai_coustics.EnhancerModel.QUAIL_VF_S, None),
        "quail_l": (ai_coustics.EnhancerModel.QUAIL_L, None),
        "quail_l_06": (ai_coustics.EnhancerModel.QUAIL_L, 0.6),
    }[condition]
    params = (
        ai_coustics.ModelParameters(enhancement_level=level)
        if level is not None
        else None
    )
    enhancer = ai_coustics.audio_enhancement(model=model, model_parameters=params)
    token = (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity("audio-bench")
        .with_grants(api.VideoGrants(room_join=True, room="audio-bench"))
        .to_jwt()
    )
    # Offline use only: the room normally provides these to the frame processor.
    enhancer._on_credentials_updated(token=token, url=os.environ["LIVEKIT_URL"])
    enhancer._on_stream_info_updated(
        room_name="audio-bench",
        participant_identity="audio-bench",
        publication_sid="TR_bench",
    )
    return enhancer


def enhance(signal: np.ndarray, condition: str) -> tuple[np.ndarray, float]:
    enhancer = make_enhancer(condition)
    pcm = (np.clip(signal, -1, 1) * 32767).astype(np.int16)
    if enhancer is None:
        return pcm, 0.0
    out, started = [], time.perf_counter()
    for i in range(0, len(pcm) - FRAME + 1, FRAME):
        frame = rtc.AudioFrame(pcm[i : i + FRAME].tobytes(), SR, 1, FRAME)
        out.append(np.frombuffer(enhancer._process(frame).data, dtype=np.int16))
    per_frame_ms = (time.perf_counter() - started) * 1000 / max(1, len(out))
    return np.concatenate(out), per_frame_ms


async def transcribe(
    session: aiohttp.ClientSession, pcm: np.ndarray
) -> list[stt.SpeechData]:
    engine = inference.STT(
        model="deepgram/nova-3",
        language="es",
        extra_kwargs={
            "diarize": True,
            "smart_format": True,
            "numerals": True,
            "keyterm": BENCH_KEYTERMS,
        },
        http_session=session,
    )
    finals: list[stt.SpeechData] = []
    async with engine.stream() as stream:

        async def feed() -> None:
            for i in range(0, len(pcm) - FRAME + 1, FRAME):
                stream.push_frame(
                    rtc.AudioFrame(pcm[i : i + FRAME].tobytes(), SR, 1, FRAME)
                )
                if i % (FRAME * 10) == 0:
                    await asyncio.sleep(0.005)
            silence = np.zeros(FRAME, dtype=np.int16).tobytes()
            for _ in range(200):
                stream.push_frame(rtc.AudioFrame(silence, SR, 1, FRAME))
                await asyncio.sleep(0.01)
            stream.end_input()

        feeder = asyncio.create_task(feed())
        async for event in stream:
            if (
                event.type == stt.SpeechEventType.FINAL_TRANSCRIPT
                and event.alternatives
            ):
                finals.append(event.alternatives[0])
        await feeder
    return finals


def wer(reference: list[str], hypothesis: list[str]) -> float:
    d = np.zeros((len(reference) + 1, len(hypothesis) + 1), dtype=int)
    d[:, 0] = np.arange(len(reference) + 1)
    d[0, :] = np.arange(len(hypothesis) + 1)
    for i, j in itertools.product(
        range(1, len(reference) + 1), range(1, len(hypothesis) + 1)
    ):
        cost = 0 if reference[i - 1] == hypothesis[j - 1] else 1
        d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + cost)
    return d[-1, -1] / max(1, len(reference))


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def score(scenario: Scenario, finals: list[stt.SpeechData]) -> dict:
    diarizer = SpeakerDiarizationService()
    utterances = [diarizer.analyze(f) for f in finals]
    reference = [
        t
        for u in sorted(scenario.utterances, key=lambda u: u.start_s)
        for t in tokens(u.text)
    ]
    hypothesis = [t for u in utterances for t in tokens(u.text)]

    def true_speaker(t: float) -> str | None:
        active = [
            u.speaker
            for u in scenario.utterances
            if u.start_s - 0.15 <= t <= u.end_s + 0.15
        ]
        return active[0] if len(active) == 1 else None

    pairs: list[tuple[str | None, str]] = []
    for final in finals:
        for word in final.words or []:
            truth = true_speaker(word.start_time)
            if truth is not None:
                pairs.append((word.speaker_id, truth))
    predicted = sorted({p for p, _ in pairs if p is not None})
    truths = sorted({t for _, t in pairs})
    best_correct = 0
    if predicted and truths:
        for perm in itertools.permutations(truths, min(len(truths), len(predicted))):
            mapping = dict(zip(predicted, perm, strict=False))
            best_correct = max(
                best_correct, sum(1 for p, t in pairs if mapping.get(p) == t)
            )
    attributable = len(pairs)
    return {
        "wer": round(wer(reference, hypothesis), 3),
        "speakers_present": len({u.speaker for u in scenario.utterances}),
        "speakers_detected": len(
            {w.speaker_id for f in finals for w in (f.words or []) if w.speaker_id}
        ),
        "speaker_attribution_acc": round(best_correct / attributable, 3)
        if attributable
        else None,
        "attributable_words": attributable,
        "words_without_speaker": sum(1 for p, _ in pairs if p is None),
        "overlap_flagged": any(u.overlap_suspected for u in utterances),
        "overlap_expected": scenario.overlap,
        "hypothesis": " | ".join(f.text for f in finals),
    }


async def main() -> None:
    load_dotenv(".env.local")
    parser = argparse.ArgumentParser()
    parser.add_argument("--conditions", default="none,quail_vf_s,quail_l")
    parser.add_argument("--scenarios", default="")
    args = parser.parse_args()
    rng = np.random.default_rng(7)
    results = []
    async with aiohttp.ClientSession() as session:
        scenarios = await build_scenarios(session)
        if args.scenarios:
            scenarios = [
                s
                for s in scenarios
                if s.name.split("_")[0] in args.scenarios.split(",")
            ]
        for scenario in scenarios:
            signal = mix(scenario, rng)
            for condition in args.conditions.split(","):
                pcm, frame_ms = enhance(signal, condition)
                finals = await transcribe(session, pcm)
                row = {
                    "scenario": scenario.name,
                    "condition": condition,
                    "enhancer_ms_per_10ms_frame": round(frame_ms, 3),
                }
                row.update(score(scenario, finals))
                results.append(row)
                print(json.dumps(row, ensure_ascii=False))
                OUT.mkdir(parents=True, exist_ok=True)
                with wave.open(
                    str(CACHE / f"{scenario.name}_{condition}.wav"), "wb"
                ) as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(SR)
                    wav.writeframes(pcm.tobytes())
    (OUT / "audio_bench.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
