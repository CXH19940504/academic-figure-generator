"""Application settings — personal-use local version."""

from functools import lru_cache
from os import getenv
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

# Project root: backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # App
    APP_NAME: str = "academic-figure-generator"
    DEBUG: bool = True
    SECRET_KEY: str = "local-dev-key"
    API_V1_PREFIX: str = "/api/v1"

    # MySQL
    DATABASE_URL: str = getenv("DATABASE_URL", "sqlite://paper_test.db")

    # Data directory (uploads, figures)
    DATA_DIR: str = str(_BACKEND_ROOT / "data")

    # Claude Agent SDK (env var: ANTHROPIC_API_KEY)
    ANTHROPIC_API_KEY: str = getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL_NAME: str = getenv("CLAUDE_MODEL_NAME", "deepseek-v4-pro")
    FIGURE_PROMPT_SKILL_NAME: str = getenv("FIGURE_PROMPT_SKILL_NAME", "academic-figure-prompt")

    # Deepseek API (env var: DEEPSEEK_API_KEY, DEEPSEEK_API_BASE)
    DEEPSEEK_API_KEY: str = getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE: str = getenv("DEEPSEEK_API_BASE", "https://api.deepseek.cn/v1")
    DEEPSEEK_MODEL: str = getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    # NanoBanana / Gemini image generation API
    # (env vars: NANOBANANA_API_KEY, NANOBANANA_API_BASE, NANOBANANA_MODEL)
    NANOBANANA_API_KEY: str = getenv("NANOBANANA_API_KEY", "")
    NANOBANANA_API_BASE: str = getenv("NANOBANANA_API_BASE", "https://api.keepgo.icu")
    NANOBANANA_MODEL: str = getenv("NANOBANANA_MODEL", "gemini-3-pro-image-preview")

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8081",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        """Parse CORS_ORIGINS from env var (JSON array string or comma-separated)."""
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                try:
                    import json

                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            # Fallback: comma-separated
            _origins = [o.strip().rstrip("/") for o in value.split(",") if o.strip()]
            return _origins or ["http://localhost:3000", "http://localhost:8081"]
        return ["http://localhost:3000", "http://localhost:8081"]

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 50

    @field_validator("API_V1_PREFIX")
    @classmethod
    def _normalize_api_prefix(cls, value: str) -> str:
        prefix = (value or "").strip()
        if not prefix:
            return "/api/v1"
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        prefix = prefix.rstrip("/")
        return prefix or "/api/v1"

    model_config = {"env_file": str(_BACKEND_ROOT.parent / ".env"), "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
