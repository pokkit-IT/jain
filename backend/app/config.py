import logging
import warnings
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET_PREFIX = "dev-secret-"

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

    # Phase 2B: shared secret for JAIN ↔ plugin service-to-service calls.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Set in .env; plugins (e.g. yardsailing) must be configured with the same value.
    JAIN_SERVICE_KEY: str = ""

    # Phase 3: comma-separated list of admin emails, for plugin install/uninstall.
    JAIN_ADMIN_EMAILS: str = ""

    @property
    def admin_emails(self) -> set[str]:
        return {
            e.strip().lower()
            for e in self.JAIN_ADMIN_EMAILS.split(",")
            if e.strip()
        }

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{_BACKEND_DIR}/jain.db"

    # Plugins
    PLUGINS_DIR: str = str((_REPO_DIR.parent / "jain-plugins" / "plugins").resolve())

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:8081", "http://localhost:19006"]


settings = Settings()

if settings.JWT_SECRET.startswith(_DEV_JWT_SECRET_PREFIX):
    msg = (
        "JAIN is running on the default dev JWT_SECRET — tokens are NOT secure. "
        "Override JWT_SECRET in .env before any non-local use. Generate with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )
    logging.getLogger("jain.config").warning(msg)
    warnings.warn(msg, stacklevel=1)

def warn_if_service_key_set(s: Settings) -> None:
    if s.JAIN_SERVICE_KEY:
        msg = (
            "JAIN_SERVICE_KEY env var is deprecated; use per-plugin service "
            "keys via POST /api/plugins/install. Legacy value will be used "
            "as a fallback for any external plugin without its own key."
        )
        logging.getLogger("jain.config").warning(msg)
        warnings.warn(msg, DeprecationWarning, stacklevel=1)


warn_if_service_key_set(settings)
