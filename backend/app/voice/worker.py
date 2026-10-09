import asyncio
import logging
import time

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)
from livekit.plugins import ai_coustics

from app.config.container import build_http_client, build_ips_service
from app.config.settings import get_settings
from app.domain.models.realtime_event import EVENTS_TOPIC
from app.emotions.emotion_analyzer import EmotionAnalyzer
from app.emotions.emotion_worker import EmotionWorker
from app.emotions.pysentimiento_classifier import PysentimientoClassifier
from app.voice.event_publisher import EventPublisher
from app.voice.ips_toolset import IpsToolset
from app.voice.prompts import GREETING_INSTRUCTIONS, SYSTEM_PROMPT
from app.voice.session_observer import SessionObserver
from app.voice.speaker_registry import SpeakerRegistry
from app.voice.transcript_tracker import TranscriptTracker

load_dotenv(".env.local")
logger = logging.getLogger("kognia.worker")

STT_MODEL = "deepgram/nova-3"
LLM_MODEL = "google/gemini-2.5-flash"
TTS_MODEL = "cartesia/sonic-3"
TTS_VOICE = "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c"
CLASSIFIER_KEY = "emotion_classifier"


def prewarm(proc: JobProcess) -> None:
    try:
        proc.userdata[CLASSIFIER_KEY] = PysentimientoClassifier()
    except Exception:
        logger.exception("could not preload emotion classifier; will retry lazily")


server = AgentServer(
    setup_fnc=prewarm,
    initialize_process_timeout=180.0,
    job_memory_warn_mb=2500,
    num_idle_processes=1,
)


def _analyzer_factory(proc: JobProcess):
    def build() -> EmotionAnalyzer | None:
        classifier = proc.userdata.get(CLASSIFIER_KEY)
        if classifier is None:
            try:
                classifier = PysentimientoClassifier()
                proc.userdata[CLASSIFIER_KEY] = classifier
            except Exception:
                logger.exception("emotion classifier failed to load")
                return None
        return EmotionAnalyzer(classifier)

    return build


@server.rtc_session(agent_name=get_settings().livekit_agent_name)
async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    session_id = ctx.room.name
    ctx.log_context_fields = {"room": session_id}
    started_at = time.monotonic()

    http_client = build_http_client()
    ips_service = build_ips_service(settings, http_client)
    warm_task = asyncio.create_task(ips_service.warm_up())

    async def send_event(text: str) -> None:
        await ctx.room.local_participant.send_text(text, topic=EVENTS_TOPIC)

    events = EventPublisher(session_id, send_event)
    tracker = TranscriptTracker(
        session_id,
        SpeakerRegistry(),
        clock_ms=lambda: int((time.monotonic() - started_at) * 1000),
    )

    session = AgentSession(
        stt=inference.STT(
            model=STT_MODEL,
            language="es",
            extra_kwargs={"diarize": True, "smart_format": True, "numerals": True},
        ),
        llm=inference.LLM(model=LLM_MODEL),
        tts=inference.TTS(model=TTS_MODEL, voice=TTS_VOICE, language="es"),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            interruption={"mode": "adaptive"},
            preemptive_generation={"enabled": True},
        ),
        max_tool_steps=4,
    )
    observer: SessionObserver
    emotions = EmotionWorker(
        _analyzer_factory(ctx.proc), on_result=lambda a: observer.on_emotion(a)
    )
    observer = SessionObserver(session, events, tracker, emotions, started_at)
    observer.attach()

    async def cleanup() -> None:
        warm_task.cancel()
        await emotions.aclose()
        await events.aclose()
        await http_client.aclose()

    ctx.add_shutdown_callback(cleanup)

    agent = Agent(instructions=SYSTEM_PROMPT, tools=[IpsToolset(ips_service, events)])
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_L
                ),
            ),
        ),
    )
    await ctx.connect()
    events.start()
    emotions.start()
    events.publish(
        "session.started",
        {"stt": STT_MODEL, "llm": LLM_MODEL, "tts": TTS_MODEL, "diarization": True},
    )
    session.generate_reply(instructions=GREETING_INSTRUCTIONS)


if __name__ == "__main__":
    cli.run_app(server)
