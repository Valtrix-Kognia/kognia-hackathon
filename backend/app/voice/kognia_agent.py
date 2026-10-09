import logging
import time
from collections.abc import AsyncIterable, AsyncIterator

from livekit import rtc
from livekit.agents import Agent, ModelSettings, StopResponse, llm, stt

from app.voice.conversation_controller import ConversationController
from app.voice.turn_manager import REPEAT_REQUEST, UNCLEAR_REQUEST

logger = logging.getLogger("kognia.agent")


class KogniaAgent(Agent):
    """Voice agent that exposes word-level STT results and gates replies per turn policy."""

    def __init__(
        self,
        *,
        instructions: str,
        tools: list[llm.Tool | llm.Toolset],
        controller: ConversationController,
    ) -> None:
        super().__init__(instructions=instructions, tools=tools)
        self._controller = controller

    async def stt_node(
        self, audio: AsyncIterable[rtc.AudioFrame], model_settings: ModelSettings
    ) -> AsyncIterator[stt.SpeechEvent]:
        async for event in Agent.default.stt_node(
            self, self._observe_audio_start(audio), model_settings
        ):
            self._observe(event)
            yield event

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        decision = self._controller.complete_turn(new_message.text_content or "")
        if decision.action == "ignore":
            raise StopResponse()
        if decision.action == "ask_repeat":
            self.session.say(
                REPEAT_REQUEST
                if decision.reason == "habla_superpuesta"
                else UNCLEAR_REQUEST,
                add_to_chat_ctx=False,
            )
            raise StopResponse()
        if decision.llm_text and decision.llm_text != new_message.text_content:
            new_message.content = [decision.llm_text]

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
