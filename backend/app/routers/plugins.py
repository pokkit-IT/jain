import logging
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.routing import Match

from app.auth.optional_user import get_current_user_optional
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


class PluginHelp(BaseModel):
    name: str
    version: str
    description: str
    help_markdown: str  # empty string if no help.md exists
    examples: list[dict]  # [{prompt, description}]


class PluginHelpResponse(BaseModel):
    plugins: list[PluginHelp]


@router.get("/help", response_model=PluginHelpResponse)
async def get_plugin_help(
    registry: PluginRegistry = Depends(get_registry),
) -> PluginHelpResponse:
    """Help content for every loaded plugin.

    - `help_markdown` is read from `help.md` in the plugin's directory if
      present. For internal plugins that's the package dir; for external
      plugins it's the install cache dir (which may or may not have one).
    - `examples` comes from the manifest's optional `examples` field —
      short tappable prompts the Help screen shows as chips.
    """
    out: list[PluginHelp] = []
    for plugin in registry.list_plugins():
        loaded = registry.get_plugin(plugin.name)
        md = ""
        if loaded is not None:
            help_path = loaded.plugin_dir / "help.md"
            if help_path.exists():
                try:
                    md = help_path.read_text(encoding="utf-8")
                except OSError:
                    md = ""
        out.append(
            PluginHelp(
                name=plugin.name,
                version=plugin.version,
                description=plugin.description,
                help_markdown=md,
                examples=[e.model_dump() for e in plugin.examples],
            )
        )
    return PluginHelpResponse(plugins=out)


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
    request: Request,
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
        return await _dispatch_internal(plugin, req, request)

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
    plugin_service_key = getattr(plugin, "service_key", None) or ""
    auth_applied = False
    if user is not None and plugin_service_key:
        headers["X-Jain-Service-Key"] = plugin_service_key
        headers["X-Jain-User-Email"] = quote(user.email, safe="@")
        headers["X-Jain-User-Name"] = quote(user.name, safe="")
        auth_applied = True

    _log.info(
        "proxy call: %s %s user=%s auth_applied=%s service_key_configured=%s",
        method,
        url,
        user.email if user else "<anonymous>",
        auth_applied,
        bool(plugin_service_key),
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
    plugin, req: "PluginCallRequest", request: Request,
) -> Response:
    """Forward the proxy call to the plugin's own router via the same
    FastAPI app instance. We construct an ASGI sub-request that targets
    the plugin's path, reusing the original Authorization header so
    get_current_user resolves the same user.

    This sidesteps re-implementing FastAPI's dependency injection machinery
    — the sub-request goes through the real router, hits the real
    Depends(get_current_user) and Depends(get_db), and comes back with
    whatever the inner route produced.
    """
    import json as _json

    method = req.method.upper()
    path = req.path
    body_bytes = _json.dumps(req.body or {}).encode("utf-8")
    auth_header = request.headers.get("authorization", "")
    _log.info(
        "internal dispatch: %s %s auth_present=%s",
        method, path, bool(auth_header),
    )

    # Build a minimal ASGI scope for the sub-request.
    headers_list: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
    ]
    if auth_header:
        headers_list.append((b"authorization", auth_header.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers_list,
        "app": request.app,
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    }

    sent_body_chunks: list[bytes] = []
    response_start: dict = {}

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            response_start.update(message)
        elif message["type"] == "http.response.body":
            sent_body_chunks.append(message.get("body", b""))

    await request.app(scope, receive, send)

    status_code = response_start.get("status", 500)
    body = b"".join(sent_body_chunks)
    # Extract content-type from response headers if available
    content_type = "application/json"
    for k, v in response_start.get("headers", []):
        if k.lower() == b"content-type":
            content_type = v.decode("utf-8")
            break

    return Response(
        content=body,
        status_code=status_code,
        media_type=content_type,
    )
