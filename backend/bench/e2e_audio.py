"""Builds microphone WAVs for the browser end-to-end runs (Chrome fake audio capture).

Each session is a timeline of spoken parts from distinct synthetic voices with silence
for the agent to answer. A reference JSON for bench/score_session.py is written next to it.
Usage: python -m bench.e2e_audio
"""

import asyncio
import json
import wave
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import numpy as np
from dotenv import load_dotenv

from bench.audio_bench import SR, noise, synthesize

OUT = Path("bench/e2e")
ANSWER_GAP_S = 17.0


@dataclass
class Part:
    speaker: str
    text: str
    pause_after_s: float = ANSWER_GAP_S
    overlap_with_next: float | None = None
    noisy: bool = False


@dataclass
class Turn:
    category: str
    parts: list[Part]
    addressed: bool
    expected: str


SESSIONS: dict[str, list[Turn]] = {
    "sesion_a": [
        Turn(
            "corta", [Part("A", "Kognia, ¿cuántas IPS hay en Caldas?")], True, "respond"
        ),
        Turn(
            "larga_con_pausa",
            [
                Part("A", "Kognia, necesito que me", pause_after_s=1.3),
                Part("A", "digas cuántos prestadores públicos hay en Antioquia."),
            ],
            True,
            "respond",
        ),
        Turn(
            "solo_palabra_activacion",
            [
                Part("A", "Kognia.", pause_after_s=2.5),
                Part("A", "¿Qué departamentos tienen más prestadores?"),
            ],
            True,
            "respond",
        ),
        Turn(
            "variante_cognia",
            [Part("A", "Cognia, busca hospitales en Armenia.")],
            True,
            "respond",
        ),
        Turn(
            "ambiental",
            [Part("B", "¿Ya almorzaron? Todavía no, después de la demo vamos.")],
            False,
            "ignore",
        ),
        Turn(
            "variante_konia",
            [Part("A", "Konia, ¿cuántas camas hay en Risaralda?")],
            True,
            "respond",
        ),
        Turn(
            "dominio_sin_activacion",
            [Part("C", "¿Cuántas sedes hay en Bogotá?")],
            True,
            "respond",
        ),
        Turn(
            "tercera_persona",
            [Part("C", "Kognia, ¿cuántas ambulancias hay en Nariño?")],
            True,
            "respond",
        ),
        Turn(
            "ambiental",
            [Part("D", "Oye, ¿viste el partido de anoche? Estuvo buenísimo.")],
            False,
            "ignore",
        ),
        Turn(
            "cuarta_persona",
            [Part("D", "Kognia, ¿qué niveles de atención aparecen en los datos?")],
            True,
            "respond",
        ),
        Turn(
            "fuera_de_fuente",
            [Part("B", "Kognia, ¿cuál es la mejor IPS de Colombia?")],
            True,
            "respond",
        ),
    ],
    "sesion_b": [
        Turn(
            "wake_repetida",
            [Part("A", "Kognia, Kognia, ¿cuántas clínicas hay en Cali?")],
            True,
            "respond",
        ),
        Turn(
            "ruido_ventilador",
            [Part("B", "Kognia, ¿cuántas IPS privadas hay en Santander?", noisy=True)],
            True,
            "respond",
        ),
        Turn(
            "voces_superpuestas",
            [
                Part(
                    "B",
                    "Kognia, ¿cuántas IPS hay en el Quindío?",
                    overlap_with_next=0.45,
                ),
                Part(
                    "C", "Yo quisiera saber qué departamentos tienen más prestadores."
                ),
            ],
            True,
            "ask_repeat_or_respond",
        ),
        Turn(
            "interrupcion",
            [
                Part(
                    "A",
                    "Kognia, ¿qué departamentos tienen más sedes y cuántas tiene cada uno?",
                    pause_after_s=4.5,
                ),
                Part("A", "Kognia, para. ¿Cuántas IPS hay en Huila?"),
            ],
            True,
            "respond",
        ),
        Turn(
            "corta", [Part("C", "Kognia, ¿cuántas IPS hay en Sucre?")], True, "respond"
        ),
        Turn(
            "ambiental",
            [Part("D", "¿Alguien tiene el cargador del portátil?")],
            False,
            "ignore",
        ),
        Turn(
            "larga_con_pausa",
            [
                Part("D", "Kognia, quisiera saber, eh,", pause_after_s=1.2),
                Part("D", "cuántas sedes de naturaleza mixta hay en todo el país."),
            ],
            True,
            "respond",
        ),
        Turn(
            "tercera_persona",
            [Part("B", "Kognia, busca la clínica San Rafael en Pasto.")],
            True,
            "respond",
        ),
        Turn(
            "variante_cognia",
            [Part("C", "Cognia, ¿cuántos consultorios hay en Boyacá?")],
            True,
            "respond",
        ),
    ],
}


async def build_session(
    session: aiohttp.ClientSession, turns: list[Turn]
) -> tuple[np.ndarray, list[dict]]:
    rng = np.random.default_rng(11)
    chunks: list[np.ndarray] = [np.zeros(int(SR * 9.0), dtype=np.float32)]
    reference: list[dict] = []
    for turn in turns:
        carry: np.ndarray | None = None
        for part in turn.parts:
            audio = await synthesize(session, part.speaker, part.text)
            if part.noisy:
                n = noise("fan", len(audio), rng).astype(np.float32)
                speech_power = np.mean(audio[np.abs(audio) > 1e-3] ** 2)
                audio = audio + n * np.sqrt(
                    speech_power / (np.mean(n**2) * 10 ** (8 / 10))
                )
            if carry is not None:
                offset = int(len(carry) * 0.45)
                mixed = np.zeros(max(len(carry), offset + len(audio)), dtype=np.float32)
                mixed[: len(carry)] += carry
                mixed[offset : offset + len(audio)] += audio
                audio, carry = mixed, None
            if part.overlap_with_next is not None:
                carry = audio
            else:
                chunks.append(audio)
                chunks.append(np.zeros(int(SR * part.pause_after_s), dtype=np.float32))
            reference.append(
                {
                    "person": part.speaker,
                    "text": part.text,
                    "addressed": turn.addressed,
                    "category": turn.category,
                    "expected": turn.expected,
                }
            )
    signal = np.concatenate(chunks)
    peak = np.abs(signal).max()
    return (signal / peak * 0.8 if peak > 0.8 else signal), reference


async def main() -> None:
    load_dotenv(".env.local")
    OUT.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        for name, turns in SESSIONS.items():
            signal, reference = await build_session(session, turns)
            path = OUT / f"{name}.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SR)
                wav.writeframes(
                    (np.clip(signal, -1, 1) * 32767).astype(np.int16).tobytes()
                )
            (OUT / f"{name}.reference.json").write_text(
                json.dumps(reference, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"{path}: {len(signal) / SR:.1f} s, {len(reference)} intervenciones")


if __name__ == "__main__":
    asyncio.run(main())
