from fastapi import Request

from app.application.services.ips_query_service import IpsQueryService
from app.application.services.session_token_service import SessionTokenService


def get_ips_service(request: Request) -> IpsQueryService:
    return request.app.state.ips_service


def get_session_service(request: Request) -> SessionTokenService:
    return request.app.state.session_service
