from fastapi import APIRouter, Depends

from app.dependencies import get_registry
from app.plugins.registry import PluginRegistry
from app.schemas.plugin import PluginListResponse

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("", response_model=PluginListResponse)
async def list_plugins(registry: PluginRegistry = Depends(get_registry)) -> PluginListResponse:
    return PluginListResponse(plugins=registry.list_plugins())
