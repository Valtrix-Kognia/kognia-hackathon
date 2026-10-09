import asyncio
import json
import logging
import time
from contextvars import ContextVar
from typing import Any

import httpx

from app.config.settings import Settings
from app.infrastructure.socrata.errors import (
    SocrataAuthError,
    SocrataError,
    SocrataQueryError,
    SocrataRateLimitError,
    SocrataResponseError,
    SocrataTimeoutError,
    SocrataUnavailableError,
)
from app.infrastructure.socrata.query_cache import QueryCache

logger = logging.getLogger("kognia.socrata")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
http_durations_ms: ContextVar[list[float] | None] = ContextVar(
    "socrata_http_durations_ms", default=None
)
MAX_PAGE_SIZE = 5000


class SocrataClient:
    """Async SODA3 client bound to one dataset. Only receives SoQL built by SoqlQuery."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        backoff_base_s: float = 0.5,
    ) -> None:
        self._settings = settings
        self._http = http_client
        self._backoff_base_s = backoff_base_s
        self._cache = QueryCache(
            ttl_s=settings.socrata_cache_ttl_s,
            max_entries=settings.socrata_cache_max_entries,
        )
        self.requests_sent = 0

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        token = self._settings.socrata_app_token
        if token and token.get_secret_value():
            headers["X-App-Token"] = token.get_secret_value()
        return headers

    async def query(
        self, soql: str, page_number: int = 1, page_size: int = 100
    ) -> list[dict[str, Any]]:
        if page_number < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError("Paginación fuera de rango")
        body = {
            "query": soql,
            "page": {"pageNumber": page_number, "pageSize": page_size},
            "includeSynthetic": False,
        }
        key = json.dumps(body, sort_keys=True, ensure_ascii=False)
        return await self._cache.get_or_load(key, lambda: self._fetch_rows(body))

    async def _fetch_rows(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        logger.info(
            "socrata query: %s (page %s)", body["query"], body["page"]["pageNumber"]
        )
        payload = await self._request("POST", self._settings.socrata_query_url, body)
        if not isinstance(payload, list) or not all(
            isinstance(r, dict) for r in payload
        ):
            raise SocrataResponseError("Expected a JSON array of objects")
        return payload

    async def metadata(self) -> dict[str, Any]:
        return await self._cache.get_or_load("__metadata__", self._fetch_metadata)

    async def _fetch_metadata(self) -> dict[str, Any]:
        payload = await self._request("GET", self._settings.socrata_metadata_url, None)
        if not isinstance(payload, dict):
            raise SocrataResponseError("Expected a JSON object for metadata")
        return payload

    async def _request(self, method: str, url: str, body: Any) -> Any:
        attempts = self._settings.socrata_max_retries + 1
        last_error: SocrataError = SocrataUnavailableError("No attempt executed")
        for attempt in range(1, attempts + 1):
            self.requests_sent += 1
            started = time.perf_counter()
            try:
                response = await self._http.request(
                    method,
                    url,
                    json=body,
                    headers=self._headers(),
                    timeout=self._settings.socrata_timeout_s,
                )
            except httpx.TimeoutException as exc:
                _record_http(started)
                raise SocrataTimeoutError("Socrata request timed out") from exc
            except httpx.TransportError as exc:
                _record_http(started)
                last_error = SocrataUnavailableError(
                    f"Transport error: {type(exc).__name__}"
                )
            else:
                _record_http(started)
                if response.status_code < 400:
                    return self._decode(response)
                last_error = self._error_for(response)
                if response.status_code not in _RETRYABLE_STATUS:
                    raise last_error
            logger.warning(
                "socrata request failed: %s (attempt %d/%d)",
                last_error,
                attempt,
                attempts,
            )
            if attempt < attempts:
                await asyncio.sleep(min(self._backoff_base_s * 2 ** (attempt - 1), 4.0))
        raise last_error

    def _decode(self, response: httpx.Response) -> Any:
        if len(response.content) > self._settings.socrata_max_response_bytes:
            raise SocrataResponseError("Response exceeds configured size limit")
        try:
            return response.json()
        except ValueError as exc:
            raise SocrataResponseError("Invalid JSON from Socrata") from exc

    @staticmethod
    def _error_for(response: httpx.Response) -> SocrataError:
        status = response.status_code
        if status in (401, 403):
            return SocrataAuthError(f"HTTP {status}")
        if status == 429:
            return SocrataRateLimitError("HTTP 429")
        if status >= 500:
            return SocrataUnavailableError(f"HTTP {status}")
        return SocrataQueryError(f"HTTP {status}: {response.text[:300]}")


def _record_http(started: float) -> None:
    durations = http_durations_ms.get()
    if durations is not None:
        durations.append((time.perf_counter() - started) * 1000)
