from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_session_service
from app.application.services.session_token_service import SessionTokenService
from app.domain.models.voice_session import VoiceSession

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
Sessions = Annotated[SessionTokenService, Depends(get_session_service)]


def _require_configured(service: SessionTokenService) -> None:
    if not service.is_configured():
        raise HTTPException(
            status_code=503, detail="El servicio de voz no está configurado."
        )


@router.post("", response_model=VoiceSession, status_code=201)
async def create_session(service: Sessions) -> VoiceSession:
    _require_configured(service)
    return service.create_session()


@router.post("/{session_id}/token", response_model=VoiceSession)
async def refresh_token(service: Sessions, session_id: str) -> VoiceSession:
    _require_configured(service)
    return service.refresh(session_id)
