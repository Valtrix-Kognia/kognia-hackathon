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
    socrata_timeout_s: float = Field(default=8.0, gt=0, le=120)
    socrata_max_retries: int = Field(default=1, ge=0, le=5)
    socrata_max_response_bytes: int = Field(default=8_000_000, gt=0)
    catalog_ttl_s: int = Field(default=6 * 3600, gt=0)
    aggregate_ttl_s: float = Field(default=1800, gt=0)
    socrata_cache_ttl_s: float = Field(default=600, ge=0)
    socrata_cache_max_entries: int = Field(default=256, gt=0)

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: SecretStr = SecretStr("")
    livekit_agent_name: str = "kognia-voice"
    noise_model: str = Field(
        default="quail_l", pattern="^(none|quail_l|quail_vf_s|quail_vf_l)$"
    )
    noise_enhancement_level: float | None = Field(default=None, ge=0, le=1)
    tool_filler_delay_s: float = Field(default=0.7, le=10)
    endpointing_min_delay_s: float = Field(default=0.5, ge=0.1, le=2.0)
    endpointing_max_delay_s: float = Field(default=3.0, ge=0.5, le=6.0)
    turn_mode: str = Field(default="wake_word", pattern="^(open|wake_word)$")
    follow_up_window_s: float = Field(default=8.0, ge=0, le=30)
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
