from datetime import datetime

from pydantic import BaseModel


class VoiceSession(BaseModel):
    session_id: str
    room_name: str
    participant_identity: str
    livekit_url: str
    token: str
    expires_at: datetime
