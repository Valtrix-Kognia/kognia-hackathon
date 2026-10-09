import json

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.config.settings import Settings
from app.infrastructure.socrata.errors import (
    SocrataAuthError,
    SocrataQueryError,
    SocrataRateLimitError,
    SocrataResponseError,
    SocrataTimeoutError,
    SocrataUnavailableError,
)
from app.infrastructure.socrata.socrata_client import SocrataClient

SETTINGS = Settings(
    _env_file=None, socrata_max_retries=2, socrata_app_token=SecretStr("tok")
)
URL = SETTINGS.socrata_query_url


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield SocrataClient(SETTINGS, http, backoff_base_s=0)


@respx.mock
async def test_query_sends_soda3_body_and_token(client: SocrataClient) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=[{"n": "1"}]))
    rows = await client.query("SELECT count(*) AS n", page_number=2, page_size=5)
    assert rows == [{"n": "1"}]
    sent = route.calls.last.request
    assert sent.headers["X-App-Token"] == "tok"
    assert json.loads(sent.content) == {
        "query": "SELECT count(*) AS n",
        "page": {"pageNumber": 2, "pageSize": 5},
        "includeSynthetic": False,
    }


@respx.mock
async def test_retries_transient_errors_then_succeeds(client: SocrataClient) -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(429),
            httpx.Response(200, json=[]),
        ]
    )
    assert await client.query("SELECT *") == []
    assert route.call_count == 3


@respx.mock
async def test_gives_up_after_max_retries(client: SocrataClient) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(500))
    with pytest.raises(SocrataUnavailableError):
        await client.query("SELECT *")
    assert route.call_count == 3


@respx.mock
async def test_rate_limit_error_after_retries(client: SocrataClient) -> None:
    respx.post(URL).mock(return_value=httpx.Response(429))
    with pytest.raises(SocrataRateLimitError):
        await client.query("SELECT *")


@pytest.mark.parametrize("status", [401, 403])
@respx.mock
async def test_auth_errors_are_not_retried(client: SocrataClient, status: int) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(status))
    with pytest.raises(SocrataAuthError):
        await client.query("SELECT *")
    assert route.call_count == 1


@respx.mock
async def test_bad_query_is_not_retried(client: SocrataClient) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(400, text="bad soql"))
    with pytest.raises(SocrataQueryError):
        await client.query("SELECT nope")
    assert route.call_count == 1


@respx.mock
async def test_timeout_is_mapped(client: SocrataClient) -> None:
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(SocrataTimeoutError):
        await client.query("SELECT *")


@respx.mock
async def test_invalid_json_shape_is_rejected(client: SocrataClient) -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"error": True}))
    with pytest.raises(SocrataResponseError):
        await client.query("SELECT *")


@respx.mock
async def test_response_size_limit() -> None:
    settings = Settings(_env_file=None, socrata_max_response_bytes=10)
    respx.post(settings.socrata_query_url).mock(
        return_value=httpx.Response(200, json=[{"x": "y" * 50}])
    )
    async with httpx.AsyncClient() as http:
        with pytest.raises(SocrataResponseError):
            await SocrataClient(settings, http).query("SELECT *")


async def test_page_bounds_are_validated(client: SocrataClient) -> None:
    with pytest.raises(ValueError):
        await client.query("SELECT *", page_size=100_000)


@respx.mock
async def test_timeout_is_not_retried(client: SocrataClient) -> None:
    route = respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(SocrataTimeoutError):
        await client.query("SELECT 1")
    assert route.call_count == 1
