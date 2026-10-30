"""
Application configuration — loaded from environment variables only.
Never put secrets in code; use .env (gitignored) or deployment env vars.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "ContextKeeper"
    APP_ENV: Literal["development", "production", "test"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./contextkeeper.db"

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FILE: str = "logs/app.log"
    AUDIT_LOG_FILE: str = "logs/audit.log"
    LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
    LOG_BACKUP_COUNT: int = 5

    # ── AI Provider ──────────────────────────────────────────────────────────
    AI_PROVIDER: Literal["gemini", "anthropic", "openai", "mock"] = "mock"
    AI_MODEL: str = ""                         # overrides per-provider default
    AI_TEMPERATURE: float = 0.2
    AI_TIMEOUT_SECONDS: int = 60
    AI_MAX_RETRIES: int = 3
    AI_MAX_INPUT_CHARS: int = 40_000           # ~10k tokens

    # Provider API keys — never logged or committed
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── Admin ────────────────────────────────────────────────────────────────
    ADMIN_TOKEN: str = "change-admin-token"

    # ── Rate limiting ────────────────────────────────────────────────────────
    AI_RATE_LIMIT_PER_MINUTE: int = 20

    # ── File upload ──────────────────────────────────────────────────────────
    UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: list[str] = Field(default=[".txt", ".md", ".pdf", ".docx"])

    # ── SMTP (optional) ──────────────────────────────────────────────────────
    SMTP_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    @field_validator("AI_PROVIDER", mode="before")
    @classmethod
    def auto_detect_provider(cls, v: str, info: object) -> str:
        """If AI_PROVIDER not set but a key is present, auto-select the provider."""
        return v  # explicit env always wins; auto-detection handled at startup

    def effective_ai_provider(self) -> str:
        """Return the active provider, auto-detecting from available keys."""
        if self.AI_PROVIDER != "mock":
            return self.AI_PROVIDER
        # Auto-detect if any key is set
        if self.GEMINI_API_KEY:
            return "gemini"
        if self.ANTHROPIC_API_KEY:
            return "anthropic"
        if self.OPENAI_API_KEY:
            return "openai"
        return "mock"


settings = Settings()

