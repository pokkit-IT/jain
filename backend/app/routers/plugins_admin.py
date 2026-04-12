import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import get_current_admin_user
from app.database import get_db
from app.dependencies import get_registry
from app.models.installed_plugin import InstalledPlugin
from app.models.user import User
from app.plugins.core.loader import LoadedPlugin
from app.plugins.core.registry import PluginRegistry
from app.plugins.core.schema import PluginManifest

router = APIRouter(prefix="/api/plugins", tags=["plugins-admin"])
_log = logging.getLogger("jain.plugins.admin")


class InstallRequest(BaseModel):
    manifest_url: str
    service_key: str


class InstallResponse(BaseModel):
    name: str
    version: str
    tools: list[str]


@router.post("/install", response_model=InstallResponse, status_code=status.HTTP_201_CREATED)
async def install_plugin(
    body: InstallRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
) -> InstallResponse:
    # 1. Fetch manifest
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(body.manifest_url)
            resp.raise_for_status()
            manifest_payload = resp.json()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"failed to fetch manifest: {type(e).__name__}: {e}",
            )

    # 2. Validate against PluginManifest schema
    try:
        manifest = PluginManifest.model_validate(manifest_payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid manifest: {e}")

    # 3. Must be external
    if manifest.type != "external":
        raise HTTPException(
            status_code=400,
            detail="only external plugins can be runtime-installed (got internal)",
        )

    # 4. Name collision check
    if registry.get_plugin(manifest.name) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"plugin name '{manifest.name}' already registered",
        )

    # 5. Extract tool names from skills
    incoming_tool_names: list[str] = []
    for skill in manifest.skills:
        incoming_tool_names.extend(skill.tools)

    # 6. Persist
    manifest_json = json.dumps(manifest.model_dump(mode="json"))
    row = InstalledPlugin(
        name=manifest.name,
        manifest_url=body.manifest_url,
        manifest_json=manifest_json,
        service_key=body.service_key,
        bundle_path=None,
        installed_by=admin.id,
    )
    db.add(row)
    await db.commit()

    # 7. Register in memory
    loaded = LoadedPlugin(
        manifest=manifest,
        plugin_dir=Path("."),
    )
    loaded.service_key = body.service_key  # type: ignore[attr-defined]
    registry.register(loaded)

    _log.info(
        "installed external plugin '%s' v%s with %d tools",
        manifest.name, manifest.version, len(incoming_tool_names),
    )

    return InstallResponse(
        name=manifest.name,
        version=manifest.version,
        tools=incoming_tool_names,
    )
