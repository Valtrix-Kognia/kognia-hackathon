"""A/B of Gemini time-to-first-chunk with the production tools, interleaving variants.

Each sample asks a question that requires a tool; the first chunk (text or tool call)
time is measured, and whether the expected tool was called is recorded, so a faster
variant that stops using tools is visible. Usage: python -m bench.llm_ttft --n 8
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
from livekit.agents import inference, llm

from app.voice.ips_toolset import IpsToolset
from app.voice.latency_metrics import percentile
from app.voice.prompts import SYSTEM_PROMPT

QUESTIONS = [
    ("¿Cuántas IPS hay en el Quindío?", "count_ips"),
    ("¿Qué departamentos tienen más prestadores?", "group_ips"),
    ("Busca hospitales en Armenia.", "search_ips"),
    ("¿Cuántas camas hay en Risaralda?", "count_ips|group_ips"),
]

COMPACT_PROMPT = (
    "Eres Kognia Voice. Respondes en español, en una a tres frases, solo con datos de las "
    "herramientas sobre IPS de Colombia (dataset oficial s2ru-bqt6). Nunca inventes cifras; "
    "si la fuente no tiene el dato, dilo. Reporta prestadores únicos y sedes. Texto plano."
)


def history(turns: int) -> list[llm.ChatMessage]:
    items: list[llm.ChatMessage] = []
    for i in range(turns):
        items.append(
            llm.ChatMessage(
                role="user", content=[f"¿Cuántas IPS hay en el departamento {i}?"]
            )
        )
        items.append(
            llm.ChatMessage(
                role="assistant",
                content=[f"Hay {100 + i} prestadores únicos y {120 + i} sedes."],
            )
        )
    return items


async def sample(
    engine: llm.LLM, prompt: str, past: int, question: str, tools: list
) -> tuple[float, str | None]:
    ctx = llm.ChatContext()
    ctx.add_message(role="system", content=prompt)
    for item in history(past):
        ctx.items.append(item)
    ctx.add_message(role="user", content=question)
    started = time.perf_counter()
    first: float | None = None
    tool: str | None = None
    async with engine.chat(chat_ctx=ctx, tools=tools) as stream:
        async for chunk in stream:
            if first is None:
                first = (time.perf_counter() - started) * 1000
            if chunk.delta and chunk.delta.tool_calls and tool is None:
                tool = chunk.delta.tool_calls[0].name
    return first or float("nan"), tool


async def main() -> None:
    load_dotenv(".env.local")
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=8)
    args = parser.parse_args()
    tools = list(IpsToolset(service=None, events=None).tools)  # type: ignore[arg-type]
    async with aiohttp.ClientSession() as session:
        variants = {
            "A_actual": (inference.LLM("google/gemini-2.5-flash"), SYSTEM_PROMPT, 1),
            "B_reasoning_none": (
                inference.LLM(
                    "google/gemini-2.5-flash", extra_kwargs={"reasoning_effort": "none"}
                ),
                SYSTEM_PROMPT,
                1,
            ),
            "C_prompt_compacto": (
                inference.LLM("google/gemini-2.5-flash"),
                COMPACT_PROMPT,
                1,
            ),
            "D_historial_20": (
                inference.LLM("google/gemini-2.5-flash"),
                SYSTEM_PROMPT,
                20,
            ),
            "E_flash_lite": (
                inference.LLM("google/gemini-2.5-flash-lite"),
                SYSTEM_PROMPT,
                1,
            ),
        }
        results: dict[str, list[dict]] = {k: [] for k in variants}
        for round_index in range(args.n):
            question, expected = QUESTIONS[round_index % len(QUESTIONS)]
            for name, (engine, prompt, past) in variants.items():
                ttft, tool = await sample(engine, prompt, past, question, tools)
                results[name].append(
                    {
                        "ttft_ms": round(ttft, 1),
                        "tool": tool,
                        "ok": bool(tool and tool in expected.split("|")),
                    }
                )
        del session
    summary = {
        name: {
            "n": len(rows),
            "ttft_p50_ms": round(percentile([r["ttft_ms"] for r in rows], 50), 1),
            "ttft_p95_ms": round(percentile([r["ttft_ms"] for r in rows], 95), 1),
            "tool_correct": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
        }
        for name, rows in results.items()
    }
    Path("bench/results/llm_ttft.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "samples": results,
                "prompt_chars": len(SYSTEM_PROMPT),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
