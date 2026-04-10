from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.dependencies import get_registry
from app.plugins.registry import PluginRegistry
from app.schemas.plugin import PluginListResponse

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("", response_model=PluginListResponse)
async def list_plugins(registry: PluginRegistry = Depends(get_registry)) -> PluginListResponse:
    return PluginListResponse(plugins=registry.list_plugins())


@router.get("/{plugin_name}/bundle", response_class=PlainTextResponse)
async def get_plugin_bundle(
    plugin_name: str,
    registry: PluginRegistry = Depends(get_registry),
) -> str:
    plugin = registry.get_plugin(plugin_name)
    if plugin is None or plugin.manifest.components is None:
        raise HTTPException(status_code=404, detail="plugin bundle not found")

    bundle_path = plugin.plugin_dir / plugin.manifest.components.bundle
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="bundle file missing on disk")
    return bundle_path.read_text(encoding="utf-8")
