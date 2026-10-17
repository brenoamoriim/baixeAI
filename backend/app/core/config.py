from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read only from environment variables."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_base_url: str = "http://localhost:3000"
    tz_reference: str = "America/Sao_Paulo"

    secret_key: str = Field(default="", min_length=0)
    signed_url_secret: str = ""
    guest_id_hmac_secret: str = ""

    database_url: str = "postgresql+psycopg://baixeai:baixeai@db:5432/baixeai"
    redis_url: str = "redis://redis:6379/0"

    storage_backend: Literal["local"] = "local"
    storage_local_root: str = "/data/storage"
    file_retention_hours: int = 2
    signed_url_ttl_seconds: int = 900

    email_provider: Literal["console", "memory"] = "console"
    email_from: str = "nao-responda@baixeai.local"

    session_ttl_days: int = 14
    cookie_secure: bool = True
    session_cookie_name: str = "baixeai_session"
    csrf_cookie_name: str = "baixeai_csrf"
    guest_cookie_name: str = "baixeai_guest"

    celery_task_always_eager: bool = False

    @model_validator(mode="after")
    def _require_secrets_outside_dev(self) -> "Settings":
        secrets = {
            "SECRET_KEY": self.secret_key,
            "SIGNED_URL_SECRET": self.signed_url_secret,
            "GUEST_ID_HMAC_SECRET": self.guest_id_hmac_secret,
        }
        weak = [name for name, value in secrets.items() if len(value) < 32]
        if weak and self.app_env == "production":
            raise ValueError(f"Missing or weak secrets in production: {', '.join(weak)}")
        if weak:
            # Development/test only: deterministic placeholders so the stack boots.
            self.secret_key = self.secret_key or "dev-secret-key-not-for-production-000000"
            self.signed_url_secret = self.signed_url_secret or "dev-signed-url-secret-not-for-prod-0000"
            self.guest_id_hmac_secret = (
                self.guest_id_hmac_secret or "dev-guest-hmac-secret-not-for-prod-0000"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
