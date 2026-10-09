from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore"
    )

    socrata_domain: str = "https://www.datos.gov.co"
    socrata_dataset_id: str = "s2ru-bqt6"
    socrata_app_token: SecretStr | None = None
    socrata_timeout_s: float = Field(default=20.0, gt=0, le=120)
    socrata_max_retries: int = Field(default=2, ge=0, le=5)
    socrata_max_response_bytes: int = Field(default=8_000_000, gt=0)
    catalog_ttl_s: int = Field(default=6 * 3600, gt=0)

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: SecretStr = SecretStr("")
    livekit_agent_name: str = "kognia-voice"
    session_token_ttl_minutes: int = Field(default=30, gt=0, le=240)

    cors_origins: list[str] = ["http://localhost:4200"]
    rate_limit_per_minute: int = Field(default=60, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def socrata_query_url(self) -> str:
        return (
            f"{self.socrata_domain}/api/v3/views/{self.socrata_dataset_id}/query.json"
        )

    @property
    def socrata_metadata_url(self) -> str:
        return f"{self.socrata_domain}/api/views/{self.socrata_dataset_id}.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
