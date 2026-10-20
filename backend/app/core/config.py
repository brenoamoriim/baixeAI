from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read only from environment variables."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    # "engine": workers that process untrusted files (light/media/ai/download). They get no secrets and no
    # database credentials at all, so a compromised engine cannot read or forge them.
    process_role: Literal["app", "engine"] = "app"
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

    # console: development log only. memory: tests. smtp: real delivery (required in production).
    email_provider: Literal["console", "memory", "smtp"] = "console"
    email_from: str = "nao-responda@baixeai.local"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_security: Literal["starttls", "ssl"] = "starttls"
    alert_email: str = ""  # operational alerts (disk, queues, errors); empty = log only

    session_ttl_days: int = 14
    cookie_secure: bool = True
    session_cookie_name: str = "baixeai_session"
    csrf_cookie_name: str = "baixeai_csrf"
    guest_cookie_name: str = "baixeai_guest"

    # Number of reverse proxies in front of the API that append to X-Forwarded-For.
    # Dev: Next.js rewrite (1). Production with Caddy -> Next -> API: set accordingly.
    trusted_proxy_hops: int = 0

    # Mercado Pago (TEST credentials outside production). Empty = payments disabled (no fake checkout).
    mp_access_token: str = ""
    mp_webhook_secret: str = ""
    mp_webhook_tolerance_seconds: int = 300
    # Public base URL Mercado Pago can reach for webhooks (a tunnel in development).
    api_public_url: str = ""

    # Hard cap on any upload request body, checked from Content-Length before reading it.
    max_upload_body_bytes: int = 96 * 1024 * 1024

    celery_task_always_eager: bool = False

    @model_validator(mode="after")
    def _require_secrets_outside_dev(self) -> "Settings":
        if self.process_role == "engine":
            # no placeholders either: anything that tries to sign/verify in an engine fails loudly
            self.secret_key = self.signed_url_secret = self.guest_id_hmac_secret = ""
            self.database_url = "postgresql+psycopg://engine-has-no-database@invalid:1/none"
            return self
        secrets = {
            "SECRET_KEY": self.secret_key,
            "SIGNED_URL_SECRET": self.signed_url_secret,
            "GUEST_ID_HMAC_SECRET": self.guest_id_hmac_secret,
        }
        weak = [name for name, value in secrets.items() if len(value) < 32]
        if weak and self.app_env == "production":
            raise ValueError(f"Missing or weak secrets in production: {', '.join(weak)}")
        if self.app_env == "production":
            if self.email_provider != "smtp" or not self.smtp_host:
                raise ValueError("Production requires EMAIL_PROVIDER=smtp and SMTP_HOST (users must get e-mails)")
            if not self.cookie_secure:
                raise ValueError("Production requires COOKIE_SECURE=true (HTTPS only)")
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
