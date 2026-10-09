import re
import secrets
from datetime import UTC, datetime, timedelta

from livekit import api

from app.config.settings import Settings
from app.domain.errors import InvalidIdentifierError
from app.domain.models.voice_session import VoiceSession

_SESSION_ID = re.compile(r"^kognia-[a-f0-9]{16}$")


class SessionTokenService:
    """Issues short-lived, room-scoped LiveKit tokens that also dispatch the Kognia agent."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(
            self._settings.livekit_url
            and self._settings.livekit_api_key
            and self._settings.livekit_api_secret.get_secret_value()
        )

    def create_session(self) -> VoiceSession:
        return self._issue(f"kognia-{secrets.token_hex(8)}")

    def refresh(self, session_id: str) -> VoiceSession:
        if not _SESSION_ID.match(session_id):
            raise InvalidIdentifierError("Identificador de sesión inválido.")
        return self._issue(session_id)

    def _issue(self, room: str) -> VoiceSession:
        ttl = timedelta(minutes=self._settings.session_token_ttl_minutes)
        identity = f"user-{secrets.token_hex(6)}"
        token = (
            api.AccessToken(
                self._settings.livekit_api_key,
                self._settings.livekit_api_secret.get_secret_value(),
            )
            .with_identity(identity)
            .with_name("Usuario")
            .with_ttl(ttl)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                    can_publish_sources=["microphone"],
                )
            )
            .with_room_config(
                api.RoomConfiguration(
                    agents=[
                        api.RoomAgentDispatch(
                            agent_name=self._settings.livekit_agent_name
                        )
                    ]
                )
            )
            .to_jwt()
        )
        return VoiceSession(
            session_id=room,
            room_name=room,
            participant_identity=identity,
            livekit_url=self._settings.livekit_url,
            token=token,
            expires_at=datetime.now(UTC) + ttl,
        )
