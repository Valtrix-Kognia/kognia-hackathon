import asyncio
import json
import logging
import time

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    STTContextOptions,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)

from app.config.container import build_http_client, build_ips_service
from app.config.settings import get_settings
from app.domain.models.realtime_event import CLIENT_METRICS_TOPIC, EVENTS_TOPIC
from app.emotions.emotion_analyzer import EmotionAnalyzer
from app.emotions.emotion_worker import EmotionWorker
from app.emotions.pysentimiento_classifier import PysentimientoClassifier
from app.voice.audio_input import build_audio_input
from app.voice.conversation_controller import ConversationController
from app.voice.event_publisher import EventPublisher
from app.voice.ips_toolset import IpsToolset
from app.voice.kognia_agent import KogniaAgent
from app.voice.latency_metrics import LatencyMetricsService
from app.voice.prompts import GREETING_INSTRUCTIONS, SYSTEM_PROMPT
from app.voice.session_observer import SessionObserver
from app.voice.speaker_diarization import SpeakerDiarizationService
from app.voice.speaker_registry import SpeakerRegistry
from app.voice.transcript_tracker import TranscriptTracker
from app.voice.turn_manager import TurnManagementService, TurnMode

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


BASE_KEYTERMS = ["Kognia", "IPS", "REPS", "prestadores", "sedes", "capacidad instalada"]
TURN_MODE_ATTRIBUTE = "kognia.turn_mode"


@server.rtc_session(agent_name=get_settings().livekit_agent_name)
async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    session_id = ctx.room.name
    ctx.log_context_fields = {"room": session_id}
    started_at = time.monotonic()
    started_wall = time.time()

    http_client = build_http_client()
    ips_service = build_ips_service(settings, http_client)

    async def send_event(text: str) -> None:
        await ctx.room.local_participant.send_text(text, topic=EVENTS_TOPIC)

    latency: LatencyMetricsService
    events = EventPublisher(
        session_id, send_event, turn_id_provider=lambda: latency.current_turn_id
    )
    latency = LatencyMetricsService(
        publish=lambda kind, data: events.publish(kind, data)
    )
    speakers = SpeakerRegistry()
    tracker = TranscriptTracker(
        session_id,
        speakers,
        clock_ms=lambda: int((time.monotonic() - started_at) * 1000),
    )
    turns = TurnManagementService(
        mode=TurnMode(settings.turn_mode),
        follow_up_window_s=settings.follow_up_window_s,
        label_for=lambda speaker: speakers.peek(speaker)[1],
    )
    emotions = EmotionWorker(
        _analyzer_factory(ctx.proc),
        on_result=lambda a: events.publish("emotion.analyzed", a),
    )
    controller = ConversationController(
        events,
        tracker,
        SpeakerDiarizationService(),
        turns,
        emotions,
        latency,
        started_wall,
    )

    session = AgentSession(
        stt=inference.STT(
            model=STT_MODEL,
            language="es",
            extra_kwargs={"diarize": True, "smart_format": True, "numerals": True},
        ),
        llm=inference.LLM(model=LLM_MODEL),
        tts=inference.TTS(model=TTS_MODEL, voice=TTS_VOICE, language="es"),
        stt_context_options=STTContextOptions(keyterms=BASE_KEYTERMS),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            endpointing={
                "min_delay": settings.endpointing_min_delay_s,
                "max_delay": settings.endpointing_max_delay_s,
            },
            interruption={
                "mode": "adaptive",
                "min_words": 2,
                "min_duration": 0.6,
                "discard_audio_if_uninterruptible": False,
                "resume_false_interruption": True,
                "false_interruption_timeout": 1.5,
            },
            preemptive_generation={"enabled": True},
        ),
        max_tool_steps=4,
    )
    observer = SessionObserver(
        session, events, tracker, controller, latency, started_at
    )
    observer.attach()
    controller.bind_current_speech(lambda: session.current_speech)
    controller.on_deferred_request(lambda text: session.generate_reply(user_input=text))

    async def warm_up() -> None:
        await ips_service.warm_up()
        territories = await ips_service.territory_names()
        session.update_options(keyterms=[*BASE_KEYTERMS, *territories])

    warm_task = asyncio.create_task(warm_up())

    def apply_turn_mode(attributes: dict[str, str]) -> None:
        raw = attributes.get(TURN_MODE_ATTRIBUTE)
        if raw in {m.value for m in TurnMode}:
            controller.set_mode(TurnMode(raw))

    def on_attributes_changed(
        changed: dict[str, str], _participant: rtc.Participant
    ) -> None:
        apply_turn_mode(changed)

    ctx.room.on("participant_attributes_changed", on_attributes_changed)

    def on_data(packet: rtc.DataPacket) -> None:
        if packet.topic != CLIENT_METRICS_TOPIC:
            return
        try:
            data = json.loads(packet.data.decode("utf-8"))
            turn_id = str(data.pop("turn_id"))
        except (ValueError, KeyError, UnicodeDecodeError):
            logger.warning("discarding malformed client metrics packet")
            return
        allowed = {k: v for k, v in data.items() if isinstance(v, int | float | str)}
        latency.on_client_metrics(turn_id, allowed)

    ctx.room.on("data_received", on_data)

    async def cleanup() -> None:
        warm_task.cancel()
        await emotions.aclose()
        await events.aclose()
        await http_client.aclose()

    ctx.add_shutdown_callback(cleanup)

    agent = KogniaAgent(
        instructions=SYSTEM_PROMPT,
        tools=[
            IpsToolset(
                ips_service,
                events,
                latency,
                filler_delay_s=settings.tool_filler_delay_s
                if settings.tool_filler_delay_s >= 0
                else None,
                request_text=lambda: controller.last_request_text,
            )
        ],
        controller=controller,
        latency=latency,
    )
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=build_audio_input(
                settings.noise_model, settings.noise_enhancement_level
            ),
        ),
    )
    await ctx.connect()
    for participant in ctx.room.remote_participants.values():
        apply_turn_mode(participant.attributes)
    events.start()
    emotions.start()
    events.publish(
        "session.started",
        {
            "stt": STT_MODEL,
            "llm": LLM_MODEL,
            "tts": TTS_MODEL,
            "diarization": True,
            "noise_model": settings.noise_model,
            "turn_mode": controller.mode.value,
        },
    )
    session.generate_reply(instructions=GREETING_INSTRUCTIONS)


if __name__ == "__main__":
    cli.run_app(server)
