import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client sliding-window limit for /api routes (in-memory, single instance)."""

    def __init__(self, app: ASGIApp, limit_per_minute: int) -> None:
        super().__init__(app)
        self._limit = limit_per_minute
        self._hits: dict[str, deque[float]] = {}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        now = time.monotonic()
        window = self._hits.setdefault(client, deque())
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self._limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Demasiadas solicitudes. Intenta de nuevo en un minuto."
                },
                headers={"Retry-After": "60"},
            )
        window.append(now)
        if len(self._hits) > 10_000:
            self._hits = {
                k: v for k, v in self._hits.items() if v and now - v[-1] <= 60
            }
        return await call_next(request)
