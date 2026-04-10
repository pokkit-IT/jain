from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_BASE_URL: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Google OAuth (sub-project A)
    GOOGLE_CLIENT_ID: str = ""

    # JAIN JWT signing (sub-project A)
    # Dev default is ≥32 bytes to satisfy pyjwt's HS256 key-length check.
    # Production must override via .env with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
    JWT_SECRET: str = "dev-secret-change-me-in-production-at-least-32-bytes"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{_BACKEND_DIR}/jain.db"

    # Plugins
    PLUGINS_DIR: str = str((_REPO_DIR.parent / "jain-plugins" / "plugins").resolve())

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:8081", "http://localhost:19006"]


settings = Settings()
