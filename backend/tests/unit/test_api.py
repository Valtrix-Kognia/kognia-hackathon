import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_ips_service
from app.application.services.ips_query_service import IpsQueryService
from app.application.services.value_catalog import ValueCatalog
from app.config.settings import Settings
from app.infrastructure.socrata.errors import SocrataTimeoutError
from app.main import create_app
from tests.unit.fake_socrata_client import FakeSocrataClient

SETTINGS = Settings(
    _env_file=None,
    livekit_url="wss://example.livekit.cloud",
    livekit_api_key="key",
    livekit_api_secret=SecretStr("secret-secret-secret-secret-1234"),
    cors_origins=["https://app.example"],
    rate_limit_per_minute=5,
)


def client_with(responses=None, settings: Settings = SETTINGS) -> TestClient:
    app = create_app(settings)
    fake = FakeSocrataClient(responses)
    service = IpsQueryService(fake, ValueCatalog(fake, 60), settings)  # type: ignore[arg-type]
    app.dependency_overrides[get_ips_service] = lambda: service
    return TestClient(app)


def test_health_reports_voice_configuration() -> None:
    with client_with() as client:
        body = client.get("/health").json()
    assert body == {"status": "ok", "voice_configured": True, "dataset": "s2ru-bqt6"}


def test_create_session_returns_scoped_token_without_secrets() -> None:
    with client_with() as client:
        response = client.post("/api/v1/sessions")
    assert response.status_code == 201
    body = response.json()
    assert body["session_id"].startswith("kognia-")
    assert "secret" not in response.text
    claims = jwt.decode(body["token"], options={"verify_signature": False})
    assert claims["video"]["room"] == body["room_name"]
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canUpdateOwnMetadata"] is True
    assert claims["roomConfig"]["agents"][0]["agentName"] == "kognia-voice"


def test_refresh_rejects_malformed_session_id() -> None:
    with client_with() as client:
        assert client.post("/api/v1/sessions/../../x/token").status_code in (400, 404)
        assert client.post("/api/v1/sessions/hack;drop/token").status_code == 400


def test_session_unavailable_when_livekit_not_configured() -> None:
    settings = Settings(_env_file=None, livekit_url="", livekit_api_key="")
    with client_with(settings=settings) as client:
        assert client.post("/api/v1/sessions").status_code == 503


def test_count_endpoint_resolves_filters() -> None:
    with client_with(
        [[{"registros": "469", "prestadores": "139", "sedes": "148"}]]
    ) as client:
        body = client.get(
            "/api/v1/ips/count", params={"departamento": "quindio"}
        ).json()
    assert body["prestadores"] == 139
    assert body["metadata"]["filters"] == {"departamento": "Quindío"}


def test_unknown_value_returns_422_with_field() -> None:
    with client_with() as client:
        response = client.get("/api/v1/ips/count", params={"departamento": "Atlantida"})
    assert response.status_code == 422
    assert response.json()["field"] == "departamento"


def test_invalid_dimension_rejected() -> None:
    with client_with() as client:
        assert (
            client.get("/api/v1/ips/group", params={"dimension": "gerente"}).status_code
            == 422
        )


def test_socrata_outage_maps_to_503_without_internals() -> None:
    with client_with() as client:
        app = client.app
        service = app.dependency_overrides[get_ips_service]()

        async def boom(_):
            raise SocrataTimeoutError("internal detail")

        service.count = boom
        response = client.get("/api/v1/ips/count")
    assert response.status_code == 503
    assert "internal detail" not in response.text


def test_cors_only_allows_configured_origin() -> None:
    with client_with() as client:
        ok = client.get("/health", headers={"Origin": "https://app.example"})
        bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "https://app.example"
    assert "access-control-allow-origin" not in bad.headers


@pytest.mark.parametrize("path", ["/api/v1/ips/count"])
def test_rate_limit(path: str) -> None:
    with client_with(
        [[{"registros": "1", "prestadores": "1", "sedes": "1"}]] * 10
    ) as client:
        codes = [client.get(path).status_code for _ in range(7)]
    assert codes[-1] == 429
