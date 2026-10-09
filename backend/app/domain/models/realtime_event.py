from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

EVENTS_TOPIC = "kognia.events"
CLIENT_METRICS_TOPIC = "kognia.client_metrics"

EventType = Literal[
    "session.started",
    "session.ended",
    "agent.listening",
    "agent.thinking",
    "agent.speaking",
    "transcript.partial",
    "transcript.final",
    "speaker.identified",
    "emotion.analyzed",
    "ips.query.started",
    "ips.query.completed",
    "ips.query.failed",
    "error.occurred",
    "metrics.turn",
    "turn.decision",
    "turn.mode",
    "metrics.client",
    "agent.interrupted",
]


class RealtimeEvent(BaseModel):
    """Envelope for every agent -> dashboard event. seq is monotonic per session."""

    type: EventType
    session_id: str
    seq: int
    turn_id: str | None = None
    emitted_at: datetime
    payload: dict[str, Any]
