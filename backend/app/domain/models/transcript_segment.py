from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SpeakerRole = Literal["user", "agent"]


class TranscriptSegment(BaseModel):
    id: str
    session_id: str
    role: SpeakerRole
    speaker_id: str
    speaker_label: str
    text: str
    start_ms: int
    end_ms: int
    is_final: bool
    interrupted: bool = False
    overlap_suspected: bool = False
    timestamp: datetime
