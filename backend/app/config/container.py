import httpx

from app.application.services.ips_query_service import IpsQueryService
from app.application.services.value_catalog import ValueCatalog
from app.config.settings import Settings
from app.infrastructure.socrata.socrata_client import SocrataClient


def build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        headers={"User-Agent": "kognia-voice/0.1"},
    )


def build_ips_service(
    settings: Settings, http_client: httpx.AsyncClient
) -> IpsQueryService:
    client = SocrataClient(settings, http_client)
    catalog = ValueCatalog(client, ttl_s=settings.catalog_ttl_s)
    return IpsQueryService(client, catalog, settings)
