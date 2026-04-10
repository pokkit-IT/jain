from fastapi import APIRouter

from app.config import settings
from app.schemas.settings import AgentSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=AgentSettings)
async def get_settings() -> AgentSettings:
    return AgentSettings(
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
    )
