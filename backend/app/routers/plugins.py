import logging
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.routing import Match

from app.auth.optional_user import get_current_user_optional
from app.config import settings
from app.dependencies import get_registry
from app.models.user import User
from app.plugins.core.registry import PluginRegistry
from app.schemas.plugin import PluginListResponse

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginCallRequest(BaseModel):
    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str  # e.g. "/api/sales" — joined with plugin.api.base_url
    body: Any = None  # JSON body for mutating methods; ignored for GET


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


_log = logging.getLogger("jain.plugins.proxy")


@router.post("/{plugin_name}/call")
async def call_plugin_api(
    plugin_name: str,
    req: PluginCallRequest,
    registry: PluginRegistry = Depends(get_registry),
    user: User | None = Depends(get_current_user_optional),
) -> Response:
    """Proxy a plugin API call from the mobile client through JAIN.

    This endpoint is invoked by plugin-rendered components (via
    PluginBridge.callPluginApi) when they need to make an HTTP call to
    their plugin's backend. Instead of calling the plugin directly from
    the browser — which hits CORS and bypasses JAIN's auth — the
    component calls this proxy, and JAIN forwards the request with the
    same service-key + user identity headers the tool executor uses.

    This mirrors the core principle from Phase 2B: authentication is a
    JAIN concern, not a plugin concern. Plugins trust JAIN, full stop.
    """
    plugin = registry.get_plugin(plugin_name)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"plugin '{plugin_name}' not found")

    # Phase 3: internal plugins are dispatched via their in-process router
    # rather than httpx. Look up the route on the plugin's registration
    # that matches (method, path) and invoke it directly.
    if plugin.manifest.type == "internal":
        return await _dispatch_internal(plugin, req, user)

    if plugin.manifest.api is None:
        raise HTTPException(
            status_code=400, detail=f"plugin '{plugin_name}' has no api base_url"
        )

    base_url = plugin.manifest.api.base_url.rstrip("/")
    url = base_url + req.path
    method = req.method.upper()

    # Build headers the same way the tool executor does (Phase 2B auth
    # pass-through via service key + URL-encoded user identity).
    headers = {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"}
    auth_applied = False
    if user is not None and settings.JAIN_SERVICE_KEY:
        headers["X-Jain-Service-Key"] = settings.JAIN_SERVICE_KEY
        headers["X-Jain-User-Email"] = quote(user.email, safe="@")
        headers["X-Jain-User-Name"] = quote(user.name, safe="")
        auth_applied = True

    _log.info(
        "proxy call: %s %s user=%s auth_applied=%s service_key_configured=%s",
        method,
        url,
        user.email if user else "<anonymous>",
        auth_applied,
        bool(settings.JAIN_SERVICE_KEY),
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method == "GET":
                resp = await client.get(url, params=req.body or {}, headers=headers)
            else:
                resp = await client.request(method, url, json=req.body, headers=headers)
        except httpx.RequestError as e:
            _log.warning("proxy request failed: %s: %s", type(e).__name__, e)
            raise HTTPException(
                status_code=502,
                detail=f"plugin request failed: {type(e).__name__}: {e}",
            )

    _log.info(
        "proxy response: %s %s -> %s (%d bytes)",
        method,
        url,
        resp.status_code,
        len(resp.content),
    )
    if resp.status_code >= 400:
        # Log the upstream body on errors so we can see what the plugin said.
        try:
            _log.warning(
                "proxy upstream %d body: %s",
                resp.status_code,
                resp.text[:500],
            )
        except Exception:
            pass

    # Forward the plugin's response back to the mobile client verbatim.
    # Keep status code intact so 401s, 422s, etc. propagate correctly.
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


async def _dispatch_internal(
    plugin, req: PluginCallRequest, user: "User | None"
) -> Response:
    """Dispatch a proxy call to an internal plugin by invoking the
    matching APIRoute on its registration.router directly.

    This preserves the mobile PluginBridge interface (POST to
    /api/plugins/{name}/call with method/path/body) while avoiding a
    real HTTP round-trip. NOTE: this is a naive dispatcher that only
    handles single-body-arg routes. Stage 3 Task 24 upgrades it to an
    ASGI sub-request for routes that use FastAPI dependencies.
    """
    import json as _json

    registration = getattr(plugin, "registration", None)
    if registration is None or registration.router is None:
        raise HTTPException(
            status_code=500,
            detail=f"internal plugin '{plugin.manifest.name}' has no router",
        )

    method = req.method.upper()
    path = req.path

    for route in registration.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if method not in route.methods:
            continue
        scope = {"type": "http", "method": method, "path": path, "headers": []}
        match, _child_scope = route.matches(scope)
        if match == Match.FULL:
            try:
                if method == "GET":
                    result = await route.endpoint()
                else:
                    result = await route.endpoint(req.body or {})
            except HTTPException as e:
                return Response(
                    content=_json.dumps({"detail": e.detail}),
                    status_code=e.status_code,
                    media_type="application/json",
                )
            return Response(
                content=(
                    _json.dumps(result)
                    if not isinstance(result, (bytes, str))
                    else result
                ),
                status_code=200,
                media_type="application/json",
            )

    raise HTTPException(
        status_code=404,
        detail=f"no route for {method} {path} on plugin '{plugin.manifest.name}'",
    )
