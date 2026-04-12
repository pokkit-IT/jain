import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
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

_MAX_BUNDLE_BYTES = 2 * 1024 * 1024  # 2 MiB


async def _fetch_and_cache_bundle(client: httpx.AsyncClient, bundle_url: str) -> bytes:
    """Fetch a plugin bundle, validating content-type and size."""
    resp = await client.get(bundle_url)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "javascript" not in content_type and "application/octet-stream" not in content_type:
        raise HTTPException(
            status_code=400,
            detail=f"bundle content-type must be JavaScript, got: {content_type!r}",
        )
    if len(resp.content) > _MAX_BUNDLE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"bundle exceeds maximum size of {_MAX_BUNDLE_BYTES} bytes",
        )
    return resp.content


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
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch manifest
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

        # 5. Extract tool names from skills and check for collisions
        incoming_tool_names: list[str] = []
        for skill in manifest.skills:
            incoming_tool_names.extend(skill.tools)

        existing_tool_names = {t.name for t in registry.all_tools()}
        for tool_name in incoming_tool_names:
            if tool_name in existing_tool_names:
                raise HTTPException(
                    status_code=409,
                    detail=f"tool name '{tool_name}' already registered by another plugin",
                )

        # 5b. Fetch and validate bundle if present
        bundle_content: bytes | None = None
        if manifest.components is not None:
            bundle_url = (
                manifest.api.base_url.rstrip("/") + "/" + manifest.components.bundle
                if manifest.api
                else manifest.components.bundle
            )
            bundle_content = await _fetch_and_cache_bundle(client, bundle_url)

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


class InstalledPluginResponse(BaseModel):
    name: str
    version: str
    manifest_url: str
    installed_at: datetime


@router.get("/installed", response_model=list[InstalledPluginResponse])
async def list_installed_plugins(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[InstalledPluginResponse]:
    result = await db.execute(select(InstalledPlugin))
    out: list[InstalledPluginResponse] = []
    for row in result.scalars().all():
        try:
            manifest = PluginManifest.model_validate_json(row.manifest_json)
        except Exception:
            continue
        out.append(InstalledPluginResponse(
            name=row.name,
            version=manifest.version,
            manifest_url=row.manifest_url,
            installed_at=row.installed_at,
        ))
    return out


@router.delete("/{plugin_name}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_plugin(
    plugin_name: str,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    registry: PluginRegistry = Depends(get_registry),
) -> None:
    row = await db.get(InstalledPlugin, plugin_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"plugin '{plugin_name}' not installed")

    if row.bundle_path:
        try:
            Path(row.bundle_path).unlink(missing_ok=True)
        except Exception as e:
            _log.warning("failed to delete bundle %s: %s", row.bundle_path, e)

    await db.delete(row)
    await db.commit()
    registry.unregister(plugin_name)
