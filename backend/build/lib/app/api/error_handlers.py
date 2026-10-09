import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError, UnknownFilterValueError
from app.infrastructure.socrata.errors import (
    SocrataAuthError,
    SocrataError,
    SocrataUnavailableError,
)

logger = logging.getLogger("kognia.api")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownFilterValueError)
    async def unknown_value(_: Request, exc: UnknownFilterValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc),
                "field": exc.field,
                "suggestions": exc.suggestions,
            },
        )

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(SocrataError)
    async def socrata_error(request: Request, exc: SocrataError) -> JSONResponse:
        logger.warning("socrata error on %s: %r", request.url.path, exc)
        status = 503 if isinstance(exc, SocrataUnavailableError) else 502
        if isinstance(exc, SocrataAuthError):
            status = 502
        return JSONResponse(status_code=status, content={"detail": exc.user_message})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "Error interno del servidor."}
        )
