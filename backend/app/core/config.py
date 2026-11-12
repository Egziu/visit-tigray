"""Typed runtime configuration. Every setting is read from the environment (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AIMode = Literal[
    "fully_local",
    "local_first_cloud_fallback",
    "cloud_assisted",
    "retrieval_only",
    "deterministic",
    "offline",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "postgresql+psycopg://postgres@localhost:5432/visit_tigray"
    redis_url: str | None = None
    secret_key: str = Field(default="dev-insecure-change-me", min_length=16)
    public_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver", "api"]
    cors_origins: list[str] = ["http://localhost:3000"]
    expose_api_docs: bool = True
    max_request_bytes: int = 25 * 1024 * 1024

    # Identity
    session_ttl_hours: int = 12
    staff_session_ttl_hours: int = 8
    require_staff_mfa: bool = True
    cookie_secure: bool = False  # forced True outside development/test, see effective_cookie_secure
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None

    # Media
    media_root: str = "./var/media"
    media_max_bytes: int = 15 * 1024 * 1024
    clamd_host: str | None = None
    clamd_port: int = 3310
    allow_unscanned_media_in_dev: bool = True
    s3_endpoint: str | None = None
    s3_bucket: str | None = None

    # AI (TIE)
    ai_default_mode: AIMode = "fully_local"
    ollama_base_url: str = "http://localhost:11434"
    llamacpp_base_url: str | None = None
    vllm_base_url: str | None = None
    cloud_ai_base_url: str | None = None
    cloud_ai_api_key: str | None = None
    cloud_ai_model: str | None = None
    local_chat_model: str = "qwen2.5:7b-instruct-q4_K_M"
    embedding_provider: Literal["hashing", "ollama"] = "hashing"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 384
    ai_timeout_seconds: float = 60.0
    # Hosts considered "local" (in addition to loopback + RFC1918) for egress policy.
    local_ai_hosts: list[str] = ["localhost", "ollama", "llamacpp", "vllm"]

    # Notifications
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    mail_from: str = "no-reply@visit-tigray.invalid"
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: list[str] = []

    # Rate limits (requests per minute)
    rate_limit_default: int = 240
    rate_limit_auth: int = 10
    rate_limit_write: int = 30
    rate_limit_ai: int = 20

    @property
    def is_dev(self) -> bool:
        return self.environment in ("development", "test")

    @property
    def effective_cookie_secure(self) -> bool:
        return True if not self.is_dev else self.cookie_secure

    def validate_for_production(self) -> list[str]:
        problems = []
        if not self.is_dev:
            if self.secret_key.startswith("dev-") or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be a strong random value (>=32 chars)")
            if not self.require_staff_mfa:
                problems.append("REQUIRE_STAFF_MFA must be true outside development")
            if self.allow_unscanned_media_in_dev and not self.clamd_host:
                problems.append("CLAMD_HOST required (malware scanning) outside development")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
