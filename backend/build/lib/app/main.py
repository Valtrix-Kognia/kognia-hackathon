import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.rate_limiter import RateLimitMiddleware
from app.api.routes import health, ips, sessions
from app.application.services.session_token_service import SessionTokenService
from app.config.container import build_http_client, build_ips_service
from app.config.settings import Settings, get_settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with build_http_client() as http_client:
            app.state.ips_service = build_ips_service(settings, http_client)
            yield

    app = FastAPI(title="Kognia Voice API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_service = SessionTokenService(settings)
    app.add_middleware(
        RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(ips.router)
    return app


app = create_app()
