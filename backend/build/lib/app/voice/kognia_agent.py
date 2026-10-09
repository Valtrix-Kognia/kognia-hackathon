import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterable, AsyncIterator

from livekit import rtc
from livekit.agents import Agent, ModelSettings, StopResponse, llm, stt

from app.voice.conversation_controller import ConversationController
from app.voice.latency_metrics import LatencyMetricsService
from app.voice.turn_manager import LISTENING_ACK, REPEAT_REQUEST, UNCLEAR_REQUEST

logger = logging.getLogger("kognia.agent")

MAX_HISTORY_ITEMS = 20
TRIMMED_HISTORY_ITEMS = 16
HOLD_EXPIRED_INSTRUCTIONS = (
    "La última intervención del usuario parece incompleta. Si con lo dicho se puede "
    "consultar la fuente, hazlo; si no, pide en una frase breve que complete la pregunta."
)


class KogniaAgent(Agent):
    """Voice agent exposing word-level STT, gating replies per turn policy and tracing
    every pipeline stage of the current turn."""

    def __init__(
        self,
        *,
        instructions: str,
        tools: list[llm.Tool | llm.Toolset],
        controller: ConversationController,
        latency: LatencyMetricsService,
    ) -> None:
        super().__init__(instructions=instructions, tools=tools)
        self._controller = controller
        self._latency = latency
        self._held_message_id: str | None = None
        self._hold_task: asyncio.Task[None] | None = None

    async def stt_node(
        self, audio: AsyncIterable[rtc.AudioFrame], model_settings: ModelSettings
    ) -> AsyncIterator[stt.SpeechEvent]:
        async for event in Agent.default.stt_node(
            self, self._observe_audio_start(audio), model_settings
        ):
            self._observe(event)
            yield event

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterator[llm.ChatChunk | str]:
        self._latency.mark("llm_start", numbered=True)
        first = True
        async for chunk in Agent.default.llm_node(
            self, chat_ctx, tools, model_settings
        ):
            if first:
                first = False
                self._latency.mark("llm_first_token", numbered=True)
            yield chunk

    async def tts_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings
    ) -> AsyncIterator[rtc.AudioFrame]:
        async def observed_text() -> AsyncIterator[str]:
            first = True
            async for piece in text:
                if first:
                    first = False
                    self._latency.mark("tts_first_text", numbered=True)
                yield piece

        first_frame = True
        async for frame in Agent.default.tts_node(
            self, observed_text(), model_settings
        ):
            if first_frame:
                first_frame = False
                self._latency.mark("tts_first_audio", numbered=True)
            yield frame

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        self._cancel_hold_timer()
        decision = self._controller.complete_turn(new_message.text_content or "")
        if decision.action == "ignore":
            raise StopResponse()
        if decision.action == "ask_repeat":
            self._say_without_llm(
                REPEAT_REQUEST
                if decision.reason == "habla_superpuesta"
                else UNCLEAR_REQUEST,
                "pidio_repetir",
            )
            raise StopResponse()
        if decision.action == "listen":
            self._held_message_id = new_message.id
            self._say_without_llm(LISTENING_ACK, "escuchando_solicitud")
            raise StopResponse()
        if decision.action == "hold":
            self._held_message_id = new_message.id
            self._hold_task = asyncio.create_task(
                self._on_hold_expired(self._controller.turns.merge_window_s)
            )
            raise StopResponse()
        if decision.merged_from:
            await self._drop_held_message()
        await self._trim_history()
        if decision.llm_text and decision.llm_text != new_message.text_content:
            new_message.content = [decision.llm_text]

    def _say_without_llm(self, text: str, outcome: str) -> None:
        handle = self.session.say(text, add_to_chat_ctx=False)
        handle.add_done_callback(lambda _h: self._latency.close_without_llm(outcome))

    async def _trim_history(self) -> None:
        """Bound prompt growth: a 20-turn history added ~260 ms TTFT (bench/llm_ttft.py)."""
        if len(self.chat_ctx.items) <= MAX_HISTORY_ITEMS:
            return
        chat_ctx = self.chat_ctx.copy()
        chat_ctx.truncate(max_items=TRIMMED_HISTORY_ITEMS)
        await self.update_chat_ctx(chat_ctx)

    async def _drop_held_message(self) -> None:
        held, self._held_message_id = self._held_message_id, None
        if held is None:
            return
        chat_ctx = self.chat_ctx.copy()
        chat_ctx.items = [item for item in chat_ctx.items if item.id != held]
        await self.update_chat_ctx(chat_ctx)

    async def _on_hold_expired(self, delay_s: float) -> None:
        await asyncio.sleep(delay_s + 0.5)
        if self._controller.turns.take_pending() is None:
            return
        self._held_message_id = None
        logger.info(
            "held request expired without continuation; answering what was said"
        )
        self.session.generate_reply(instructions=HOLD_EXPIRED_INSTRUCTIONS)

    def _cancel_hold_timer(self) -> None:
        if self._hold_task and not self._hold_task.done():
            self._hold_task.cancel()
        self._hold_task = None

    async def on_exit(self) -> None:
        self._cancel_hold_timer()
        with contextlib.suppress(Exception):
            await super().on_exit()

    async def _observe_audio_start(
        self, audio: AsyncIterable[rtc.AudioFrame]
    ) -> AsyncIterator[rtc.AudioFrame]:
        first = True
        async for frame in audio:
            if first:
                first = False
                self._controller.on_audio_started(time.time() - frame.duration)
            yield frame

    def _observe(self, event: stt.SpeechEvent) -> None:
        if not event.alternatives:
            return
        try:
            if event.type == stt.SpeechEventType.INTERIM_TRANSCRIPT:
                self._controller.on_interim(event.alternatives[0])
            elif event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                self._controller.on_final(event.alternatives[0])
        except Exception:
            logger.exception("failed to process STT event for the dashboard")
