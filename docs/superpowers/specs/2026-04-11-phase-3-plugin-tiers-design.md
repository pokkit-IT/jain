# Phase 3: Plugin Tiers — Internal and External

**Date:** 2026-04-11
**Status:** Design approved, ready for implementation plan
**Supersedes:** Late-Phase-2B assumption that yardsailing is an external HTTP service

## Goal

Replace JAIN's current "yardsailing is an external HTTP service we proxy to" model with a first-class plugin system that has two tiers:

- **Internal plugins** — first-party Python packages that run in JAIN's own process. Trusted, fast, share the database directly. Yardsailing becomes the first internal plugin.
- **External plugins** — third-party services that JAIN proxies to over HTTP. Sandboxed by process/machine isolation. Installable at runtime without restarting JAIN.

Rewrite yardsailing as a clean first-party internal plugin inside JAIN. Keep the external tier as the path for any third-party plugin — same mechanism we built in Phase 2B, just generalized and made runtime-installable.

## Architecture

```
                      ┌──────────────────────────────┐
                      │     JAIN Mobile (Expo)       │
                      │   chat + tool calls + UI     │
                      └──────────────┬───────────────┘
                                     │ HTTPS + JWT
                      ┌──────────────▼───────────────┐
                      │      JAIN Backend (FastAPI)  │
                      │                              │
                      │  ┌────────────────────────┐  │
                      │  │   PluginRegistry       │  │
                      │  │   (mutable, DB-backed) │  │
                      │  └────┬──────────────┬────┘  │
                      │       │              │       │
                      │  ┌────▼────┐   ┌────▼────┐  │
                      │  │Internal │   │External │  │
                      │  │ Loader  │   │ Loader  │  │
                      │  └────┬────┘   └────┬────┘  │
                      │       │             │       │
                      │  in-process      HTTP proxy │
                      │  Python pkg      via existing│
                      │  (yardsailing)   /call route │
                      └──────────┬──────────────┬────┘
                                 │              │
                     ┌───────────▼─┐   ┌───────▼──────────┐
                     │ JAIN SQLite │   │ Third-party      │
                     │ (shared)    │   │ plugin service   │
                     │ users,      │   │ (any language,   │
                     │ yardsailing_│   │ any host)        │
                     │  sales, …   │   └──────────────────┘
                     └─────────────┘
```

**Key architectural commitments:**

1. **Security by default.** Untrusted code never runs in JAIN's process. Third-party plugins always go through the external tier's HTTP proxy.
2. **Trusted first-party escape hatch.** First-party code can run in-process with full DB access, because JAIN's maintainer wrote it and trusts it. WordPress/Django-app model.
3. **Zero-friction authoring.** A plugin is "a manifest + some code that matches an interface." No proprietary SDK, no submission queue.
4. **Runtime install for external plugins.** Internal plugins ship with a JAIN deployment. External plugins come and go without restarting.
5. **YAGNI on process sandboxing.** The external HTTP tier IS our sandbox. No subprocess workers, no WASM, no thread pools per plugin.

**Tech stack:** Same as current JAIN — FastAPI, SQLAlchemy async, Pydantic v2, SQLite (single shared DB), pytest, React Native + Expo on the mobile side. No new runtime dependencies.

## Background and motivation

Phase 2B built an auth pass-through mechanism: JAIN verifies a user's identity once, then forwards trusted headers (`X-Jain-Service-Key`, `X-Jain-User-Email`, `X-Jain-User-Name`) to plugin backends so plugins don't need to touch JWTs. This worked well in principle.

The breaking point: yardsailing was treated as an external HTTP service at `api.yardsailing.sale`. When a user tried to create a sale through the JAIN mobile app, the request flow was:

```
Mobile → JAIN /api/plugins/yardsailing/call
     → JAIN's httpx proxy
     → https://api.yardsailing.sale/api/sales (with service-key headers)
     → 401 (production yardsailing didn't have the Phase 2B branch deployed)
```

But the deeper issue wasn't deployment — it was conceptual. Yardsailing is not a third-party service that JAIN happens to integrate with. It's the first plugin built for JAIN, authored by the same person, deployed on the same infrastructure, trusted the same. Treating it as a third-party HTTP service imposed cross-origin, network-hop, and deployment costs with zero corresponding isolation benefit.

The right fix is architectural: split plugins into two tiers based on trust, and put yardsailing in the trusted tier.

## The two-tier plugin model

| Tier | What it is | Who writes it | Install method | Isolation |
|---|---|---|---|---|
| **Internal** | Python package imported into JAIN's process. Shares DB session, event loop, memory. | JAIN's maintainer, or people directly trusted. Ships as part of a JAIN release. | Requires a JAIN deployment. Not runtime-loadable. | None — plugin runs inside JAIN. |
| **External** | Standalone HTTP service. Any language, any framework. JAIN proxies to it via `/api/plugins/{name}/call`. | Anyone. Plugin author owns its deployment. | **Runtime install via manifest URL.** No JAIN restart. | Full process/machine isolation. |

The tool executor, chat service, UI component renderer, and mobile app don't care about the tier — they query plugins generically. The tier only matters at load time and at tool-invocation dispatch time.

## Internal plugin shape

An internal plugin is a Python package at `jain/backend/app/plugins/<name>/`.

### Directory layout

```
jain/backend/app/plugins/yardsailing/
├── __init__.py          # exports: register() -> PluginRegistration
├── plugin.json          # manifest (same schema external plugins use)
├── models.py            # SQLAlchemy models — Sale, Photo, etc.
├── routes.py            # FastAPI APIRouter with the plugin's HTTP endpoints
├── services.py          # business logic (create_sale, list_sales_near, …)
├── tools.py             # ToolDef definitions the LLM sees
├── components/          # optional — UI component source
│   └── SaleForm.tsx
├── bundle/              # optional — pre-built JS bundle
│   └── yardsailing.js
└── tests/
    └── test_sales.py
```

### Registration interface

Each internal plugin's `__init__.py` exposes a single function:

```python
# jain/backend/app/plugins/yardsailing/__init__.py
from app.plugins.types import PluginRegistration
from .routes import router
from .tools import TOOLS

def register() -> PluginRegistration:
    return PluginRegistration(
        name="yardsailing",
        version="1.0.0",
        type="internal",
        router=router,              # mounted at /api/plugins/yardsailing/*
        tools=TOOLS,                # List[ToolDef] the LLM can invoke
        ui_bundle_path="bundle/yardsailing.js",  # relative to plugin dir
        ui_components=["SaleForm"],
    )
```

Plugin authors don't subclass anything, don't register hooks, don't implement lifecycle callbacks. They return a dataclass describing what their plugin offers. JAIN's loader does the rest.

### Loader behavior at JAIN startup

1. Walk `app/plugins/*/` looking for packages whose `__init__.py` defines `register()`.
2. Import each one and call `register()`.
3. Take the returned `PluginRegistration` and:
   - Mount the plugin's router under `/api/plugins/{name}/…`
   - Add each `ToolDef` to the global tool registry
   - Register the UI bundle path so `/api/plugins/{name}/bundle` can serve it
   - Store the `PluginRegistration` in the mutable `PluginRegistry`
4. If a plugin's `register()` raises, log WARNING and continue. One bad plugin must not prevent JAIN from starting.

### Database access

Plugin models import JAIN's shared `Base` and declare tables with the plugin name as a prefix:

```python
# jain/backend/app/plugins/yardsailing/models.py
from app.db.base import Base
from app.models.user import User
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

class Sale(Base):
    __tablename__ = "yardsailing_sales"
    id: Mapped[str] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str]
    address: Mapped[str]
    description: Mapped[str | None]
    start_date: Mapped[str]
    end_date: Mapped[str | None]
    start_time: Mapped[str]
    end_time: Mapped[str]
    owner: Mapped[User] = relationship()
```

Because models import the shared `Base`, they're automatically picked up by JAIN's Alembic `env.py` when `alembic revision --autogenerate` runs. Plugin authors use JAIN's normal migration workflow.

### Authentication

Internal plugin routes use FastAPI's dependency injection directly:

```python
from app.auth.dependencies import get_current_user
from app.models.user import User

@router.post("/sales")
async def create_sale(
    body: CreateSaleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ...
```

No service keys, no header forwarding, no trust handshake — the plugin is inside JAIN's trust boundary.

### Tools

Tool definitions live in `tools.py` and use the existing `ToolDef` schema with one new field — `handler`, a Python callable invoked directly by the tool executor:

```python
# jain/backend/app/plugins/yardsailing/tools.py
from app.plugins.types import ToolDef
from .services import create_sale_handler

TOOLS = [
    ToolDef(
        name="create_yard_sale",
        description="Create a new yard sale listing",
        input_schema={...},
        auth_required=True,
        handler=create_sale_handler,
    ),
    ToolDef(
        name="show_sale_form",
        description="Show the yard sale creation form to the user",
        input_schema={},
        ui_component="SaleForm",
    ),
]
```

The tool executor's dispatch becomes: **if `tool.handler` is set, call it as an async Python function; else proxy over HTTP to `tool.endpoint`.** The fork is a single conditional.

### Two dispatch paths: LLM tool calls vs. UI component calls

An internal plugin exposes operations via two mechanisms, which are independent:

1. **LLM-callable tools.** Declared in `tools.py` as `ToolDef` entries with a Python `handler` callable. The chat loop's tool executor invokes these when the LLM decides to call a tool. This path does not touch HTTP — it's a direct function call inside JAIN's process.

2. **UI-component HTTP routes.** Declared in `routes.py` as a standard FastAPI `APIRouter`. Used by UI components (like `SaleForm`) that need to make REST-style calls with a method/path/body shape. The existing `PluginBridge.callPluginApi(path, method, body)` mobile API is preserved unchanged: it POSTs to `/api/plugins/{name}/call`, and the proxy endpoint dispatches internally for internal plugins (by looking up the matching route on the plugin's router) or proxies over HTTP for external plugins.

Keeping both paths means the existing mobile `PluginBridge` interface, the `SaleForm` component's call signature, and the `/api/plugins/{name}/call` proxy endpoint all carry forward from Phase 2B without changes. The only new thing at the HTTP layer is: when the proxy endpoint sees an internal plugin, instead of `httpx.request(base_url + path, ...)`, it walks the plugin's router looking for a route that matches `(method, path)` and invokes the handler directly.

**A note on tool vs. route boundaries.** An operation can be both a tool AND a route — e.g., `create_yard_sale` is both an LLM-callable tool (for direct creation) and a UI route at `POST /sales` (for form submission). In that case, both the `ToolDef.handler` and the `APIRouter` route call into the same underlying service function in `services.py`. The plugin declares the operation once as a service and wires it up at two entry points. No duplication of business logic.

## External plugin shape and runtime install

External plugins use the same manifest schema as internal plugins, with different fields populated. The `type` field is the discriminator.

### Unified manifest schema

```json
{
  "name": "weather",
  "version": "1.0.0",
  "type": "external",
  "description": "Weather lookup for any location",
  "author": "Jane Dev <jane@example.com>",

  "api": {
    "base_url": "https://weather-plugin.example.com"
  },

  "tools": [
    {
      "name": "get_weather",
      "description": "Get current weather for a location",
      "input_schema": {...},
      "endpoint": "/api/weather",
      "method": "GET",
      "auth_required": false
    }
  ],

  "components": {
    "bundle": "https://weather-plugin.example.com/bundle.js",
    "exports": ["WeatherCard"]
  }
}
```

Internal plugins have `"type": "internal"`, omit `api.base_url`, and their tools omit `endpoint`/`method` (the Python handler is wired up by code in `tools.py`, not the manifest).

### Install flow

```
POST /api/plugins/install         (admin only)
{
  "manifest_url": "https://weather-plugin.example.com/plugin.json",
  "service_key": "<admin-generated shared secret>"
}

1. JAIN fetches {manifest_url}
2. JAIN validates the manifest against the pydantic schema
3. JAIN checks: type == "external", name doesn't collide, tool names don't collide
4. If components.bundle is present, JAIN fetches the JS bundle, content-type checks,
   size-limit checks (2MB max), writes to data/plugins/{name}/bundle.js
5. Optional health probe: GET {base_url}/health (warn if missing, don't fail)
6. INSERT into installed_plugins table
7. registry.add(plugin) — plugin is immediately visible to the tool executor
8. Return 201 with plugin name, version, and tool list
```

### Endpoints

- `POST /api/plugins/install` — admin only, body: `{manifest_url, service_key}`, returns 201 with registered plugin summary
- `GET /api/plugins/installed` — admin only, lists external plugins currently in the registry
- `DELETE /api/plugins/{name}` — admin only, uninstalls an external plugin
- `GET /api/plugins` — unchanged from Phase 2B, lists all plugins (internal + external) visible to a chat session

### Validation at install time

1. Manifest URL is reachable and returns valid JSON parsing against `PluginManifest`
2. `type == "external"` — internal plugins cannot be runtime-installed
3. Plugin `name` does not collide with an existing registered plugin (either tier)
4. Every tool in `tools[]` has a `name` that does not collide with any existing tool in the global registry
5. If `components.bundle` is declared, the bundle URL is reachable, content-type is `application/javascript` (or `text/javascript`), body size ≤ 2 MiB
6. Optional: health probe `GET {base_url}/health` — warn on failure, do not reject

Any validation failure returns 4xx with a specific error message. The plugin is not added to the registry or persisted.

### Install persistence

```python
class InstalledPlugin(Base):
    __tablename__ = "installed_plugins"
    name: Mapped[str] = mapped_column(primary_key=True)
    manifest_url: Mapped[str]
    manifest_json: Mapped[str]       # cached copy of last-fetched manifest
    service_key: Mapped[str]         # sent as X-Jain-Service-Key per proxied call
    bundle_path: Mapped[str | None]  # local path to cached UI bundle
    installed_at: Mapped[datetime]
    installed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
```

At JAIN startup, after internal plugins load from the filesystem, the external loader reads `installed_plugins` and registers each row from its cached `manifest_json`. No re-fetch — JAIN trusts what's in the DB because it was validated at install time.

### Per-plugin service keys

Each installed external plugin has its own service key, generated by the admin at install time and stored on the `installed_plugins` row. The global `JAIN_SERVICE_KEY` environment variable is retired. Rationale: a compromised plugin's service key does not give attackers access to other plugins.

### Uninstall

`DELETE /api/plugins/{name}` removes the `installed_plugins` row, deletes the cached bundle file, and removes the plugin from the in-memory registry. In-flight tool calls complete normally. The next request that tries to call a tool from the uninstalled plugin gets a 404 from the tool executor.

### Upgrade

Uninstall + reinstall. No version migration path in Phase 3.

## Database and migrations

- **One SQLite file, shared across JAIN core and all internal plugins.**
- Internal plugin tables are prefixed with the plugin name (`yardsailing_sales`, `yardsailing_photos`).
- Plugin `models.py` imports JAIN's `Base` so models register on the shared metadata automatically.
- JAIN's Alembic config sees plugin models via normal autogenerate. Plugin authors run `alembic revision --autogenerate` from JAIN's root.
- The `installed_plugins` table is part of JAIN core's schema and gets its own migration in JAIN's regular sequence.

**Caveat:** A plugin with a broken SQLAlchemy model definition will fail at import time, which propagates to JAIN's startup. Mitigation: the plugin loader catches import errors per plugin, logs them at WARNING, and skips the broken plugin. JAIN continues to start. The cost of this trade-off is that broken plugins silently disappear from the registry rather than loudly failing. That is the correct trade-off because the alternative — one bad plugin takes down JAIN — is strictly worse.

## Admin permission model

```python
# app/config.py
class Settings(BaseSettings):
    JAIN_ADMIN_EMAILS: str = ""   # comma-separated

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.JAIN_ADMIN_EMAILS.split(",") if e.strip()}


# app/auth/admin.py
def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.email.lower() not in settings.admin_emails:
        raise HTTPException(403, "admin only")
    return user
```

- Admins are configured via the `JAIN_ADMIN_EMAILS` env var — comma-separated list, set before JAIN starts.
- Install, uninstall, and list-installed endpoints depend on `get_current_admin_user` instead of `get_current_user`.
- First admin is configured by editing `.env`. Adding more admins is an env edit plus restart.
- No DB column, no migration, no admin UI for Phase 3. Upgrade to a role column later if needed by OR-ing env and DB roles.

## Mobile app changes

Two small pieces; everything else stays as-is.

**1. Plugin refresh.** Add a second refresh trigger to the existing `useHydratePlugins` hook in `App.tsx`: re-call `listPlugins()` when the chat tab gains focus (via `useFocusEffect`) and when the app returns to foreground (via `AppState` listener). A newly-installed plugin's tools and components appear within a few seconds without an app restart.

**2. No in-app install UI.** Admins install external plugins via `curl` or a minimal web form. Building an in-app install screen is real work (list available plugins, validate URLs, manage service keys, error handling) and YAGNI for Phase 3.

**What does NOT change:**
- Tool executor response handling (`display_hint: "component:..."` still routes the same way)
- `PluginBridge` interface
- `useChat`'s `auth_required` retry path
- `AuthPrompt` inline sign-in
- `PluginHost` dynamic bundle loader
- `/api/plugins/{name}/call` proxy endpoint (still used for external plugins)

All of the Phase 2B mobile work carries forward unchanged. The tier split is a pure backend concern.

## Migration plan (Phase 2B → Phase 3)

Five stages, each leaving JAIN in a working state.

### Stage 1: Backend groundwork (non-breaking)

- Add `type: "internal" | "external"` to `PluginManifest`, default `"external"` so existing manifests parse unchanged
- Add `handler: Callable | None` to `ToolDef`, optional and unused in Stage 1
- Refactor `PluginRegistry` to be mutable: expose `register(plugin)`, `unregister(name)`; keep read path unchanged
- Split the loader into `InternalPluginLoader` and `ExternalPluginLoader`; both still load from the existing filesystem path
- Add empty `installed_plugins` Alembic migration (table exists, unused)
- Full existing test suite passes

**End state:** JAIN starts, yardsailing still works as an external HTTP plugin pointing at `api.yardsailing.sale`, nothing user-visible changes. Pure refactor.

### Stage 2: Internal plugin scaffolding

- Create `jain/backend/app/plugins/` directory with filesystem-scan loader
- Define `PluginRegistration` dataclass and the `register()` interface
- Fork the tool executor: `if tool.handler: await tool.handler(...); else: proxy over HTTP`
- Write a throwaway `_hello` internal plugin with one tool (`hello_world` → returns `"hi"`) to prove the loader, registry, and executor integration end-to-end
- Tests: internal loader discovery, plugin registration, tool executor dispatch fork, `hello_world` round-trip through chat
- Delete `_hello` at the end of the stage

**End state:** JAIN supports both tiers. Yardsailing is still external. Internal machinery validated.

### Stage 3: Yardsailing clean rewrite as internal plugin

Do this in one focused sitting — mid-stage, yardsailing works as neither external nor internal.

- Create `jain/backend/app/plugins/yardsailing/` with the standard layout
- Write fresh `models.py` using JAIN's `Base` and FK to `users.id` — `yardsailing_sales` table with `owner_id`, `title`, `address`, dates, times, description
- Write fresh `routes.py` using `Depends(get_current_user)` directly; no cookie auth, no service-key branch, no trusted headers
- Write fresh `services.py` with `create_sale`, `list_sales_near`, `get_sale_by_id`
- Write fresh `tools.py` with `create_yard_sale` and `show_sale_form` as `ToolDef` instances; `create_yard_sale` has a Python `handler`, `show_sale_form` has `ui_component="SaleForm"`
- Copy `SaleForm.tsx` from `jain-plugins/plugins/yardsailing/src/` into `jain/backend/app/plugins/yardsailing/components/`
- Build the UI bundle and commit it at `jain/backend/app/plugins/yardsailing/bundle/yardsailing.js`
- Write `plugin.json` with `"type": "internal"`, tool descriptors, UI component exports
- Add Alembic migration for `yardsailing_sales`
- Remove yardsailing from `jain-plugins/plugins/` (keep the repo alive for now)
- End-to-end test: chat → "create a yard sale" → form renders → fill → submit → row exists in JAIN's SQLite → Jain confirms in chat

**End state:** Yardsailing lives entirely inside JAIN. The external HTTP mechanism is no longer used by any plugin; the code remains.

### Stage 4: External tier runtime install

- Add `/api/plugins/install`, `/api/plugins/installed`, `/api/plugins/{name}` DELETE endpoints
- Add `get_current_admin_user` dependency and `JAIN_ADMIN_EMAILS` env var
- Add startup reader that loads external plugins from the `installed_plugins` table
- Add per-plugin service-key storage on `installed_plugins.service_key`
- Update the tool executor's external-proxy path to look up per-plugin service keys instead of reading global `settings.JAIN_SERVICE_KEY`
- Deprecate `JAIN_SERVICE_KEY` env var: log a WARNING if still set, don't fail
- Write a throwaway external plugin locally (10-line FastAPI service with one tool) and test install/call/uninstall end-to-end
- Delete the throwaway plugin when done

**End state:** Both tiers fully operational. Yardsailing runs internally. External install proven by a test plugin.

### Stage 5: Cleanup and repo hygiene

- Remove `JAIN_SERVICE_KEY` from `config.py`, `.env.example`, and any remaining code references
- Strip `jain-plugins` repo: delete `plugins/yardsailing/`, keep `tools/build.ts` and the esbuild config, add `examples/hello-external/` (a minimal reference external plugin), write an SDK README explaining how to author a plugin
- Archive the `yardsailing` repo on GitHub: push a final commit with a README pointing at JAIN, flip to read-only
- Shut down `api.yardsailing.sale` deployment whenever safe
- Update JAIN's main README with the new plugin model

**End state:** Three clean homes for plugin code — JAIN repo for core + first-party internal plugins, `jain-plugins` repo as the developer SDK, third-party plugin authors own their own repos. No stray service keys. No orphan repos.

### What carries forward from Phase 2B unchanged

- Tool executor's `auth_required` gate and `__source: "jain_executor_gate"` sentinel
- URL-encoded user identity headers for external plugins
- `get_current_user_optional` dependency
- `chat_service` display-hint handling (`auth_required`, `component:...`)
- `context_builder` user identity injection
- Mobile `AuthPrompt` inline sign-in
- Mobile `useChat` auth retry path (both the direct callback and the `useEffect` fallback)
- Mobile `PluginHost` dynamic bundle loader with `require` shim
- Mobile `/api/plugins/{name}/call` POST endpoint — still used for external plugins
- `useFocusEffect` refocus on tab switch
- `googleAuth.ts` with `ResponseType.IdToken` and `prompt: "select_account"`

Phase 2B was not wasted work. It was the mechanism for the external tier; the external tier is still part of the final design.

## Explicitly out of scope

Phase 3 is narrowly focused on making the plugin system structurally sound. It is deliberately not the foundation for a public plugin ecosystem. The following are explicitly NOT part of Phase 3:

- **Plugin marketplace or discovery registry.** Revisit when there are more than ~3 plugins.
- **In-app install UI.** Install via `curl` or minimal web form. Revisit when the ecosystem demands it.
- **Plugin versioning / upgrade path.** Upgrade = uninstall + reinstall.
- **Subprocess, thread-pool, or WASM sandboxing.** External HTTP tier IS the sandbox.
- **Cross-plugin communication.** Route through JAIN's core if ever needed.
- **Fine-grained per-tool authz.** `auth_required` is a single bit.
- **Per-plugin rate limiting, quotas, or billing hooks.**
- **Signed plugin manifests or code signing.** Install trusts admin credentials.
- **Plugin lifecycle hooks (onInstall, onUninstall, onUpgrade).** Plugins are stateless from JAIN's perspective.
- **Mobile app discovery of plugin-defined settings screens.** Plugins that need config expose their own settings UI component accessed through chat.
- **Data migration from `api.yardsailing.sale` production DB.** Clean rewrite starts fresh.

Each of these has a specific trigger that would justify revisiting it. Without that trigger, none of them ship in Phase 3.

## Success criteria

Phase 3 is complete when:

1. A user can open JAIN mobile, sign in with Google, say "create a yard sale," fill out the form, and see the sale persisted in JAIN's SQLite database — with no HTTP round-trip leaving JAIN's process for yardsailing code.
2. An admin can POST to `/api/plugins/install` with a manifest URL and immediately see the installed plugin's tools usable in chat, without restarting JAIN.
3. An admin can DELETE an installed external plugin and immediately see its tools disappear from chat.
4. The `yardsailing` repo is archived. The `jain-plugins` repo is stripped down to the SDK.
5. `JAIN_SERVICE_KEY` env var no longer exists. Each installed external plugin has its own service key in the database.
6. JAIN's test suite — including tests for both tiers of the plugin loader, tool executor dispatch fork, install/uninstall flow, and yardsailing-specific model and route behavior — passes.
