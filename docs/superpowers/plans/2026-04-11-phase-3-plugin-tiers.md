# Phase 3: Plugin Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "yardsailing as external HTTP service" model with a two-tier plugin architecture. Rewrite yardsailing as a first-party internal plugin inside JAIN. Make the external tier runtime-installable.

**Architecture:** Two plugin tiers. Internal plugins are Python packages under `jain/backend/app/plugins/<name>/` that share JAIN's process, database, and trust boundary. External plugins are HTTP services installed at runtime via a manifest URL, stored in an `installed_plugins` table, and proxied through `/api/plugins/{name}/call`. The tool executor dispatches to either Python handlers (internal) or HTTP proxy (external) based on plugin type.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, pyjwt, SQLite (single shared DB), pytest, React Native + Expo SDK 54, TypeScript, Zustand, esbuild.

---

## Pre-flight notes for the executor

Two state mismatches between the spec and the current code base that every task below is written against:

1. **No Alembic in this repo.** `app/database.py` uses `Base.metadata.create_all()` inside the `lifespan` context. The spec references "Alembic migration for `installed_plugins`" and "`add_yardsailing_sales_table` migration" but those don't map onto anything that exists. This plan substitutes: (a) importing plugin models into `app/models/__init__.py` (or the plugin loader) so `create_all` picks them up, and (b) rewriting the stub `InstalledPlugin` model already at `backend/app/models/installed_plugin.py`. If Alembic is introduced later, these schemas are Alembic-ready.
2. **`app/plugins/` collision.** `app/plugins/` currently holds `schema.py`, `registry.py`, `loader.py`. The spec's convention is `app/plugins/<plugin_name>/` for plugin packages. Resolution: move the core files to `app/plugins/core/` (Task 7) so `app/plugins/yardsailing/` can be a plugin package without colliding. All existing imports of `app.plugins.registry` etc. get updated in the same task.
3. **`db.base`/`db.session` imports in the spec do not exist.** The repo uses `app.models.base.Base` and `app.database.get_db`. Every task uses the real paths.

---

## Stage 1: Backend groundwork (non-breaking)

### Task 1: Add `type` field to `PluginManifest`

**Files:**
- Modify: `backend/app/plugins/schema.py`
- Test: `backend/tests/test_plugin_schema.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_plugin_schema.py`:

```python
def test_plugin_manifest_type_defaults_to_external():
    from app.plugins.schema import PluginManifest

    m = PluginManifest(
        name="w", version="1", description="d", skills=[],
    )
    assert m.type == "external"


def test_plugin_manifest_type_accepts_internal():
    from app.plugins.schema import PluginManifest

    m = PluginManifest(
        name="y", version="1", description="d", skills=[], type="internal",
    )
    assert m.type == "internal"


def test_plugin_manifest_type_rejects_garbage():
    import pytest
    from pydantic import ValidationError
    from app.plugins.schema import PluginManifest

    with pytest.raises(ValidationError):
        PluginManifest(
            name="x", version="1", description="d", skills=[], type="totally-wrong",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugin_schema.py::test_plugin_manifest_type_defaults_to_external -v`
Expected: FAIL with `AttributeError: 'PluginManifest' object has no attribute 'type'` or equivalent.

- [ ] **Step 3: Add the field**

Edit `backend/app/plugins/schema.py`. Change the import line to include `Literal`:

```python
from typing import Any, Literal
```

Change `PluginManifest` to:

```python
class PluginManifest(BaseModel):
    name: str
    version: str
    description: str
    author: str = ""
    type: Literal["internal", "external"] = "external"
    skills: list[SkillDef]
    components: PluginComponents | None = None
    api: PluginApi | None = None
    assets: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_plugin_schema.py -v`
Expected: PASS on the three new tests and all pre-existing tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/schema.py backend/tests/test_plugin_schema.py
git commit -m "feat(plugins): add type discriminator to PluginManifest"
```

---

### Task 2: Add `handler` callable to `ToolDef`

**Files:**
- Modify: `backend/app/plugins/schema.py`
- Test: `backend/tests/test_plugin_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_plugin_schema.py`:

```python
def test_tool_def_handler_defaults_to_none():
    from app.plugins.schema import ToolDef, ToolInputSchema

    t = ToolDef(name="x", description="d", input_schema=ToolInputSchema())
    assert t.handler is None


def test_tool_def_handler_accepts_async_callable():
    from app.plugins.schema import ToolDef, ToolInputSchema

    async def h(args, user=None, db=None):
        return {"ok": True}

    t = ToolDef(
        name="x", description="d", input_schema=ToolInputSchema(), handler=h,
    )
    assert t.handler is h
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugin_schema.py::test_tool_def_handler_defaults_to_none -v`
Expected: FAIL with attribute error on `handler`.

- [ ] **Step 3: Add the field**

Edit `backend/app/plugins/schema.py`. Update the top of the file and `ToolDef`:

```python
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolInputSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: ToolInputSchema
    # Optional: endpoint path on the plugin's api.base_url. Defaults to /{tool.name}.
    endpoint: str = ""
    # HTTP method. Defaults to GET. Use POST/PUT/DELETE for write operations.
    method: str = "GET"
    # Phase 2B: when True, the tool executor refuses to call this tool
    # unless the user is authenticated.
    auth_required: bool = False
    # Phase 2B: when set, the tool is a "client-side UI tool".
    ui_component: str | None = None
    # Phase 3: when set, the tool executor calls this Python callable
    # directly instead of making an HTTP request. Used by internal plugins.
    # Signature: async def handler(args: dict, user: User | None, db: AsyncSession) -> Any
    handler: Callable[..., Awaitable[Any]] | None = Field(default=None, exclude=True)
```

The `exclude=True` keeps `handler` out of serialized manifest JSON so `/api/plugins` responses stay clean.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_plugin_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/schema.py backend/tests/test_plugin_schema.py
git commit -m "feat(plugins): add ToolDef.handler callable for internal plugins"
```

---

### Task 3: Rewrite `InstalledPlugin` model to match spec

**Files:**
- Modify: `backend/app/models/installed_plugin.py`
- Test: `backend/tests/test_installed_plugin_model.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_installed_plugin_model.py`:

```python
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.installed_plugin import InstalledPlugin
from app.models.user import User


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_installed_plugin_has_spec_columns(session: AsyncSession):
    user = User(
        id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
    )
    session.add(user)
    await session.flush()

    plugin = InstalledPlugin(
        name="weather",
        manifest_url="https://example.com/plugin.json",
        manifest_json='{"name":"weather"}',
        service_key="sk-1234",
        bundle_path=None,
        installed_at=datetime.utcnow(),
        installed_by=user.id,
    )
    session.add(plugin)
    await session.commit()

    got = await session.get(InstalledPlugin, "weather")
    assert got is not None
    assert got.manifest_url == "https://example.com/plugin.json"
    assert got.service_key == "sk-1234"
    assert got.bundle_path is None
    assert got.installed_by == user.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_installed_plugin_model.py -v`
Expected: FAIL — current model columns are `id, name, version, enabled`, not the spec shape.

- [ ] **Step 3: Rewrite the model**

Replace the entire contents of `backend/app/models/installed_plugin.py`:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class InstalledPlugin(Base):
    """Persistence for runtime-installed external plugins.

    Internal plugins are discovered from the filesystem and never written
    to this table. External plugins are installed via POST /api/plugins/install
    and each installation gets a row here. On startup, the external plugin
    loader reads this table and registers each row from its cached manifest.
    """

    __tablename__ = "installed_plugins"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    manifest_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    service_key: Mapped[str] = mapped_column(String(256), nullable=False)
    bundle_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    installed_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_installed_plugin_model.py -v`
Expected: PASS.

- [ ] **Step 5: Also run the full suite to confirm no consumer depends on the old columns**

Run: `cd backend && pytest -x`
Expected: PASS (no other code currently touches `InstalledPlugin`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/installed_plugin.py backend/tests/test_installed_plugin_model.py
git commit -m "refactor(models): rewrite InstalledPlugin to match phase 3 spec"
```

---

### Task 4: Make `PluginRegistry` mutable with `register` / `unregister`

**Files:**
- Modify: `backend/app/plugins/registry.py`
- Test: `backend/tests/test_plugin_registry.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_plugin_registry.py`:

```python
def test_registry_register_adds_plugin(tmp_path):
    from app.plugins.loader import LoadedPlugin
    from app.plugins.registry import PluginRegistry
    from app.plugins.schema import PluginManifest

    r = PluginRegistry(plugins_dir=tmp_path)
    manifest = PluginManifest(
        name="dynamic", version="1", description="d", skills=[],
    )
    loaded = LoadedPlugin(manifest=manifest, plugin_dir=tmp_path)
    r.register(loaded)

    assert r.get_plugin("dynamic") is loaded
    assert "dynamic" in [p.name for p in r.list_plugins()]


def test_registry_unregister_removes_plugin(tmp_path):
    from app.plugins.loader import LoadedPlugin
    from app.plugins.registry import PluginRegistry
    from app.plugins.schema import PluginManifest

    r = PluginRegistry(plugins_dir=tmp_path)
    manifest = PluginManifest(
        name="dynamic", version="1", description="d", skills=[],
    )
    r.register(LoadedPlugin(manifest=manifest, plugin_dir=tmp_path))
    r.unregister("dynamic")

    assert r.get_plugin("dynamic") is None
    assert "dynamic" not in [p.name for p in r.list_plugins()]


def test_registry_unregister_missing_name_is_noop(tmp_path):
    from app.plugins.registry import PluginRegistry

    r = PluginRegistry(plugins_dir=tmp_path)
    r.unregister("never-existed")  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_plugin_registry.py::test_registry_register_adds_plugin -v`
Expected: FAIL — `PluginRegistry` has no `register` method.

- [ ] **Step 3: Add mutable methods**

Edit `backend/app/plugins/registry.py`, adding these methods to `PluginRegistry`:

```python
    def register(self, plugin: LoadedPlugin) -> None:
        """Add a plugin to the in-memory registry at runtime.

        Used by the external loader on startup and by POST /api/plugins/install.
        Overwrites any existing plugin with the same name.
        """
        self._plugins[plugin.manifest.name] = plugin

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry. No-op if the name is unknown."""
        self._plugins.pop(name, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_plugin_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/registry.py backend/tests/test_plugin_registry.py
git commit -m "feat(plugins): make PluginRegistry mutable with register/unregister"
```

---

### Task 5: Drop `lru_cache` from dependencies so mutable registry actually mutates

**Files:**
- Modify: `backend/app/dependencies.py`

- [ ] **Step 1: Verification-first — read current caching**

The registry is cached via `@lru_cache(maxsize=1)`. This is fine for startup-loaded plugins but will bite us in Stage 4 when `/api/plugins/install` mutates the registry from a different request context. The cache itself is not the problem (it's a module-level singleton cache, not per-request) but we must guarantee the same instance is returned across the install endpoint and the chat service. Verify current behavior: singleton is shared.

Run: `cd backend && python -c "from app.dependencies import get_registry; a=get_registry(); b=get_registry(); print(a is b)"`
Expected: `True`.

- [ ] **Step 2: Add a helper that exposes the raw singleton for mutation**

Edit `backend/app/dependencies.py`. Append:

```python
def reset_registry_for_tests() -> None:
    """Clear the cached registry singleton. Tests only."""
    _registry_singleton.cache_clear()
    _chat_service_singleton.cache_clear()
```

No behavior change for production — just a test hook. The existing `@lru_cache` is kept because it DOES return the same instance to every caller.

- [ ] **Step 3: Verify**

Run: `cd backend && pytest -x`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/dependencies.py
git commit -m "chore(deps): expose reset_registry_for_tests helper"
```

---

### Task 6: Run full Phase 2B test suite to confirm Stage 1 is non-breaking

**Files:**
- None — verification only.

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && pytest -v`
Expected: All Phase 2B tests pass. If anything fails, STOP and investigate before proceeding — Stage 1 must be non-breaking.

- [ ] **Step 2: Run the backend in dev mode for 30 seconds**

Run: `cd backend && uvicorn app.main:app --port 8000` (Ctrl+C after 30 s).
Expected: No errors at startup. `[App] loaded plugins: ['yardsailing']` in logs (it still loads the old external manifest from `../jain-plugins/plugins`).

- [ ] **Step 3: No commit — this is a verification step, nothing changed.**

---

## Stage 2: Internal plugin scaffolding

### Task 7: Move core plugin files to `app/plugins/core/`

**Files:**
- Create: `backend/app/plugins/__init__.py`
- Create: `backend/app/plugins/core/__init__.py`
- Move: `backend/app/plugins/schema.py` → `backend/app/plugins/core/schema.py`
- Move: `backend/app/plugins/registry.py` → `backend/app/plugins/core/registry.py`
- Move: `backend/app/plugins/loader.py` → `backend/app/plugins/core/loader.py`
- Modify: every file that imports `app.plugins.schema`, `app.plugins.registry`, `app.plugins.loader`

**Rationale:** The spec wants `app/plugins/<name>/` for plugin packages, but we already have `app/plugins/schema.py` etc. Moving the core files to `app/plugins/core/` eliminates the namespace collision without breaking anything.

- [ ] **Step 1: Find all call sites**

Run: `cd backend && grep -rn "app.plugins.schema\|app.plugins.registry\|app.plugins.loader\|from .schema\|from .loader\|from .registry" app tests`

Expected output lists every file that needs updating. Make a note — the set is roughly:
- `app/dependencies.py`
- `app/engine/tool_executor.py`
- `app/routers/plugins.py`
- `app/schemas/plugin.py`
- `app/services/chat_service.py`
- `app/services/context_builder.py`
- `tests/test_plugin_loader.py`
- `tests/test_plugin_registry.py`
- `tests/test_plugin_schema.py`
- `tests/test_tool_executor.py`
- Internal cross-references inside `app/plugins/registry.py` and `app/plugins/loader.py`.

- [ ] **Step 2: Create the new package layout**

Create `backend/app/plugins/__init__.py` with empty contents (just an empty file — the package marker).

Create `backend/app/plugins/core/__init__.py`:

```python
from .loader import LoadedPlugin, load_plugin, load_plugins_from_dir
from .registry import PluginRegistry
from .schema import (
    PluginApi,
    PluginComponents,
    PluginManifest,
    SkillDef,
    ToolDef,
    ToolInputSchema,
)

__all__ = [
    "LoadedPlugin",
    "load_plugin",
    "load_plugins_from_dir",
    "PluginRegistry",
    "PluginApi",
    "PluginComponents",
    "PluginManifest",
    "SkillDef",
    "ToolDef",
    "ToolInputSchema",
]
```

- [ ] **Step 3: Move the three files**

```bash
git mv backend/app/plugins/schema.py backend/app/plugins/core/schema.py
git mv backend/app/plugins/registry.py backend/app/plugins/core/registry.py
git mv backend/app/plugins/loader.py backend/app/plugins/core/loader.py
```

- [ ] **Step 4: Fix intra-package imports**

Inside `backend/app/plugins/core/registry.py`, the `from .loader import ...` and `from .schema import ...` lines already use relative imports and still resolve inside `core/` — no change needed.

Inside `backend/app/plugins/core/loader.py`, same story.

- [ ] **Step 5: Update all external call sites with `replace_all`**

In each of the files listed in Step 1, replace:
- `from app.plugins.schema` → `from app.plugins.core.schema`
- `from app.plugins.registry` → `from app.plugins.core.registry`
- `from app.plugins.loader` → `from app.plugins.core.loader`
- `import app.plugins.schema` → `import app.plugins.core.schema`
- (and similar)

The specific files and lines:

`backend/app/dependencies.py`: `from .plugins.registry import PluginRegistry` → `from .plugins.core.registry import PluginRegistry`

`backend/app/engine/tool_executor.py`: `from app.plugins.registry import PluginRegistry` → `from app.plugins.core.registry import PluginRegistry`

`backend/app/routers/plugins.py`: `from app.plugins.registry import PluginRegistry` → `from app.plugins.core.registry import PluginRegistry`

`backend/app/schemas/plugin.py`: whatever references `app.plugins.schema` gets bumped to `app.plugins.core.schema`.

`backend/app/services/chat_service.py`: `from app.plugins.registry import PluginRegistry` → `from app.plugins.core.registry import PluginRegistry`

`backend/app/services/context_builder.py`: same.

`backend/tests/test_plugin_loader.py`: `from app.plugins.loader import ...` → `from app.plugins.core.loader import ...`

`backend/tests/test_plugin_registry.py`: `from app.plugins.registry import PluginRegistry` → `from app.plugins.core.registry import PluginRegistry`. Any `from app.plugins.loader` likewise.

`backend/tests/test_plugin_schema.py`: `from app.plugins.schema import ...` → `from app.plugins.core.schema import ...`

`backend/tests/test_tool_executor.py`: `from app.plugins.registry import PluginRegistry` → `from app.plugins.core.registry import PluginRegistry`.

- [ ] **Step 6: Run the full test suite**

Run: `cd backend && pytest -x -v`
Expected: All tests still pass. If any test fails on an import error, grep again for stragglers:
`cd backend && grep -rn "app\.plugins\.schema\|app\.plugins\.registry\|app\.plugins\.loader" app tests`

- [ ] **Step 7: Commit**

```bash
git add backend/app/plugins/ backend/app/dependencies.py backend/app/engine/tool_executor.py backend/app/routers/plugins.py backend/app/schemas/plugin.py backend/app/services/chat_service.py backend/app/services/context_builder.py backend/tests/test_plugin_loader.py backend/tests/test_plugin_registry.py backend/tests/test_plugin_schema.py backend/tests/test_tool_executor.py
git commit -m "refactor(plugins): move core files to app/plugins/core/ to free app/plugins/<name>/"
```

---

### Task 8: Define `PluginRegistration` dataclass and plugin types module

**Files:**
- Create: `backend/app/plugins/core/types.py`
- Modify: `backend/app/plugins/core/__init__.py`
- Test: `backend/tests/test_plugin_types.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_plugin_types.py`:

```python
def test_plugin_registration_dataclass_shape():
    from fastapi import APIRouter
    from app.plugins.core.schema import ToolDef, ToolInputSchema
    from app.plugins.core.types import PluginRegistration

    router = APIRouter()
    tool = ToolDef(name="t", description="d", input_schema=ToolInputSchema())

    reg = PluginRegistration(
        name="demo",
        version="1.0.0",
        type="internal",
        router=router,
        tools=[tool],
        ui_bundle_path="bundle/demo.js",
        ui_components=["DemoCard"],
    )

    assert reg.name == "demo"
    assert reg.type == "internal"
    assert reg.router is router
    assert reg.tools == [tool]
    assert reg.ui_bundle_path == "bundle/demo.js"
    assert reg.ui_components == ["DemoCard"]


def test_plugin_registration_optional_fields_default():
    from app.plugins.core.types import PluginRegistration

    reg = PluginRegistration(
        name="x", version="1", type="internal",
    )
    assert reg.router is None
    assert reg.tools == []
    assert reg.ui_bundle_path is None
    assert reg.ui_components == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugin_types.py -v`
Expected: FAIL with `ModuleNotFoundError: app.plugins.core.types`.

- [ ] **Step 3: Create the types module**

Create `backend/app/plugins/core/types.py`:

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from .schema import ToolDef

if TYPE_CHECKING:
    from fastapi import APIRouter


@dataclass
class PluginRegistration:
    """What an internal plugin's `register()` function returns.

    The loader uses this to wire the plugin's router into the FastAPI app,
    register tools with the global registry, and serve the plugin's UI
    bundle over `/api/plugins/{name}/bundle`.
    """

    name: str
    version: str
    type: Literal["internal", "external"]
    router: "APIRouter | None" = None
    tools: list[ToolDef] = field(default_factory=list)
    ui_bundle_path: str | None = None
    ui_components: list[str] = field(default_factory=list)
```

Update `backend/app/plugins/core/__init__.py` to re-export:

```python
from .loader import LoadedPlugin, load_plugin, load_plugins_from_dir
from .registry import PluginRegistry
from .schema import (
    PluginApi,
    PluginComponents,
    PluginManifest,
    SkillDef,
    ToolDef,
    ToolInputSchema,
)
from .types import PluginRegistration

__all__ = [
    "LoadedPlugin",
    "load_plugin",
    "load_plugins_from_dir",
    "PluginRegistry",
    "PluginApi",
    "PluginComponents",
    "PluginManifest",
    "PluginRegistration",
    "SkillDef",
    "ToolDef",
    "ToolInputSchema",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_plugin_types.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/core/types.py backend/app/plugins/core/__init__.py backend/tests/test_plugin_types.py
git commit -m "feat(plugins): add PluginRegistration dataclass"
```

---

### Task 9: Split loader into `InternalPluginLoader` and `ExternalPluginLoader`

**Files:**
- Create: `backend/app/plugins/core/loaders.py`
- Test: `backend/tests/test_plugin_loaders.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_plugin_loaders.py`:

```python
from pathlib import Path

from app.plugins.core.loaders import ExternalPluginLoader, InternalPluginLoader
from app.plugins.core.registry import PluginRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_internal_loader_discovers_package_with_register_function(tmp_path):
    # Build a tiny plugin package on disk
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from app.plugins.core.types import PluginRegistration\n"
        "def register():\n"
        "    return PluginRegistration(name='demo', version='1', type='internal')\n"
    )
    # Empty marker that makes the package importable via the loader's machinery.
    (pkg / "plugin.json").write_text('{"name":"demo","version":"1","type":"internal",'
                                     '"description":"d","skills":[]}')

    registry = PluginRegistry(plugins_dir=tmp_path)
    loader = InternalPluginLoader(plugins_dir=tmp_path)
    loader.load_all(registry)

    plugin = registry.get_plugin("demo")
    assert plugin is not None
    assert plugin.manifest.name == "demo"
    assert plugin.manifest.type == "internal"


def test_external_loader_reads_existing_filesystem_path(tmp_path):
    """Stage 1 behavior: the external loader still reads the jain-plugins
    filesystem path. Eventually (Stage 4) it will read from the DB."""
    registry = PluginRegistry(plugins_dir=FIXTURES)
    loader = ExternalPluginLoader(plugins_dir=FIXTURES)
    loader.load_all(registry)

    names = [p.name for p in registry.list_plugins()]
    assert "yardsailing" in names
    assert "small-talk" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugin_loaders.py -v`
Expected: FAIL on `ModuleNotFoundError: app.plugins.core.loaders`.

- [ ] **Step 3: Implement loaders**

Create `backend/app/plugins/core/loaders.py`:

```python
"""Two plugin loaders: internal (Python packages with register()) and
external (manifest-based HTTP services).

Both share the same `load_all(registry)` entry point and the same output
shape — a `LoadedPlugin` per plugin added to the registry. The dispatch
fork is in `ToolExecutor`, not here.
"""

import importlib.util
import logging
import sys
from pathlib import Path

from .loader import LoadedPlugin, load_plugins_from_dir
from .registry import PluginRegistry
from .schema import PluginManifest
from .types import PluginRegistration

_log = logging.getLogger("jain.plugins.loader")


class InternalPluginLoader:
    """Walks a directory of Python packages, imports each one, and calls
    its `register()` function to obtain a `PluginRegistration`.
    """

    def __init__(self, plugins_dir: Path | str):
        self.plugins_dir = Path(plugins_dir)

    def load_all(self, registry: PluginRegistry) -> None:
        if not self.plugins_dir.exists():
            return

        for child in sorted(self.plugins_dir.iterdir()):
            if not child.is_dir() or not (child / "__init__.py").exists():
                continue
            try:
                self._load_one(child, registry)
            except Exception as e:
                _log.warning(
                    "internal plugin '%s' failed to load: %s: %s",
                    child.name, type(e).__name__, e,
                )

    def _load_one(self, pkg_dir: Path, registry: PluginRegistry) -> None:
        name = pkg_dir.name
        if name.startswith("_") and name != "_hello":
            # Skip private helpers unless it's the Stage-2 test plugin.
            return

        module_name = f"app.plugins.{name}"
        # Prefer normal import (if the package is already on sys.path via
        # app.plugins.<name>). Fall back to spec-based loading for plugins
        # that live outside app/plugins/.
        try:
            module = __import__(module_name, fromlist=["register"])
        except ModuleNotFoundError:
            spec = importlib.util.spec_from_file_location(
                module_name, pkg_dir / "__init__.py",
            )
            if spec is None or spec.loader is None:
                raise
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        if not hasattr(module, "register"):
            _log.info("internal plugin '%s' has no register() — skipping", name)
            return

        registration: PluginRegistration = module.register()

        manifest_path = pkg_dir / "plugin.json"
        if manifest_path.exists():
            manifest = PluginManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8"),
            )
        else:
            manifest = PluginManifest(
                name=registration.name,
                version=registration.version,
                description=f"internal plugin {registration.name}",
                type="internal",
                skills=[],
            )

        loaded = LoadedPlugin(
            manifest=manifest,
            plugin_dir=pkg_dir,
            tools=list(registration.tools),
        )
        # Stash the registration on the LoadedPlugin for the dispatcher.
        loaded.registration = registration  # type: ignore[attr-defined]
        registry.register(loaded)


class ExternalPluginLoader:
    """Stage 1: still reads the jain-plugins filesystem path.
    Stage 4: reads the installed_plugins DB table instead.
    """

    def __init__(self, plugins_dir: Path | str):
        self.plugins_dir = Path(plugins_dir)

    def load_all(self, registry: PluginRegistry) -> None:
        for plugin in load_plugins_from_dir(self.plugins_dir):
            # Only load plugins whose manifest says external (or legacy,
            # where type defaults to external).
            if plugin.manifest.type != "external":
                continue
            registry.register(plugin)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_plugin_loaders.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/core/loaders.py backend/tests/test_plugin_loaders.py
git commit -m "feat(plugins): split loader into InternalPluginLoader/ExternalPluginLoader"
```

---

### Task 10: Wire loaders into `dependencies.py` startup path

**Files:**
- Modify: `backend/app/dependencies.py`
- Test: `backend/tests/test_plugin_loaders.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_plugin_loaders.py`:

```python
def test_get_registry_runs_both_loaders(monkeypatch, tmp_path):
    """get_registry() should invoke both InternalPluginLoader.load_all
    and ExternalPluginLoader.load_all on the shared registry."""
    from app import dependencies
    from app.plugins.core.registry import PluginRegistry

    dependencies.reset_registry_for_tests()
    monkeypatch.setattr(dependencies.settings, "PLUGINS_DIR", str(tmp_path))

    internal_called = {"v": False}
    external_called = {"v": False}

    real_internal = dependencies.InternalPluginLoader
    real_external = dependencies.ExternalPluginLoader

    class SpyInternal(real_internal):
        def load_all(self, registry: PluginRegistry) -> None:
            internal_called["v"] = True
            return super().load_all(registry)

    class SpyExternal(real_external):
        def load_all(self, registry: PluginRegistry) -> None:
            external_called["v"] = True
            return super().load_all(registry)

    monkeypatch.setattr(dependencies, "InternalPluginLoader", SpyInternal)
    monkeypatch.setattr(dependencies, "ExternalPluginLoader", SpyExternal)

    dependencies.get_registry()

    assert internal_called["v"]
    assert external_called["v"]

    dependencies.reset_registry_for_tests()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugin_loaders.py::test_get_registry_runs_both_loaders -v`
Expected: FAIL (loaders aren't wired yet).

- [ ] **Step 3: Rewrite `_registry_singleton`**

Edit `backend/app/dependencies.py`:

```python
from functools import lru_cache
from pathlib import Path

from .config import settings
from .engine.anthropic_provider import AnthropicProvider
from .engine.base import LLMProvider
from .engine.tool_executor import ToolExecutor
from .plugins.core.loaders import ExternalPluginLoader, InternalPluginLoader
from .plugins.core.registry import PluginRegistry
from .services.chat_service import ChatService


@lru_cache(maxsize=1)
def _registry_singleton() -> PluginRegistry:
    reg = PluginRegistry(plugins_dir=settings.PLUGINS_DIR)
    # Internal plugins live inside JAIN's own source tree.
    internal_dir = Path(__file__).parent / "plugins"
    InternalPluginLoader(plugins_dir=internal_dir).load_all(reg)
    # External plugins: Stage 1 still reads the jain-plugins filesystem path.
    # Stage 4 will replace this with DB-backed loading.
    ExternalPluginLoader(plugins_dir=settings.PLUGINS_DIR).load_all(reg)
    return reg


def get_registry() -> PluginRegistry:
    return _registry_singleton()


def _make_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic":
        return AnthropicProvider(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.LLM_MODEL,
        )
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")


@lru_cache(maxsize=1)
def _chat_service_singleton() -> ChatService:
    registry = get_registry()
    provider = _make_provider()
    executor = ToolExecutor(registry=registry)
    return ChatService(registry=registry, provider=provider, tool_executor=executor)


def get_chat_service() -> ChatService:
    return _chat_service_singleton()


def reset_registry_for_tests() -> None:
    _registry_singleton.cache_clear()
    _chat_service_singleton.cache_clear()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_plugin_loaders.py -v`
Expected: PASS.

Run: `cd backend && pytest -x`
Expected: All tests pass. Note that startup-time plugin loading from `tests/fixtures/plugins/` is NOT touched here — individual tests use their own `PluginRegistry` instances.

- [ ] **Step 5: Commit**

```bash
git add backend/app/dependencies.py backend/tests/test_plugin_loaders.py
git commit -m "feat(plugins): wire internal+external loaders into registry singleton"
```

---

### Task 11: Fork tool executor on `tool.handler`

**Files:**
- Modify: `backend/app/engine/tool_executor.py`
- Test: `backend/tests/test_tool_executor.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_tool_executor.py`:

```python
async def test_execute_calls_handler_for_internal_tool():
    """When tool.handler is set, the executor invokes it as an async
    function instead of making an HTTP call."""
    from app.engine.base import ToolCall
    from app.engine.tool_executor import ToolExecutor
    from app.plugins.core.loader import LoadedPlugin
    from app.plugins.core.registry import PluginRegistry
    from app.plugins.core.schema import PluginManifest, ToolDef, ToolInputSchema

    called = {}

    async def handler(args, user=None, db=None):
        called["args"] = args
        called["user"] = user
        return {"greeting": "hi"}

    tool = ToolDef(
        name="hello_world",
        description="hi",
        input_schema=ToolInputSchema(),
        handler=handler,
    )
    manifest = PluginManifest(
        name="_hello", version="1", description="d", skills=[], type="internal",
    )
    plugin = LoadedPlugin(manifest=manifest, plugin_dir=Path("."), tools=[tool])

    registry = PluginRegistry(plugins_dir=Path("."))
    registry.register(plugin)

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="hello_world", arguments={"who": "world"}),
        user=None,
    )

    assert called["args"] == {"who": "world"}
    assert json.loads(result.content) == {"greeting": "hi"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tool_executor.py::test_execute_calls_handler_for_internal_tool -v`
Expected: FAIL — executor still tries to read `plugin.manifest.api` and errors on the internal plugin.

- [ ] **Step 3: Fork the executor**

Edit `backend/app/engine/tool_executor.py`. In the `execute` method, insert this block immediately after the `ui_component` branch and BEFORE the `if plugin.manifest.api is None:` check:

```python
        # Phase 3: internal plugins have a Python handler set on the tool.
        # Call it directly instead of making an HTTP request. Auth gating
        # still applies — internal handlers receive user=None for anonymous
        # callers and decide what to do.
        if tool.handler is not None:
            if tool.auth_required and user is None:
                return ToolResult(
                    tool_call_id=call.id,
                    content=json.dumps({
                        "error": "auth_required",
                        "plugin": plugin.manifest.name,
                        "__source": "jain_executor_gate",
                    }),
                )
            try:
                payload = await tool.handler(call.arguments, user=user, db=None)
            except Exception as e:
                return ToolResult(
                    tool_call_id=call.id,
                    content=json.dumps({
                        "error": f"handler failed: {type(e).__name__}",
                        "detail": str(e),
                    }),
                )
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps(payload) if not isinstance(payload, str) else payload,
            )
```

Note: `db=None` here is a temporary placeholder. Stage 3 introduces a DB-session injection mechanism when we wire the yardsailing handler to a real SQLAlchemy session.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_tool_executor.py -v`
Expected: PASS on the new test AND all Phase 2B tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/tool_executor.py backend/tests/test_tool_executor.py
git commit -m "feat(executor): fork tool dispatch on ToolDef.handler for internal plugins"
```

---

### Task 12: Inject `AsyncSession` into tool handler calls

**Files:**
- Modify: `backend/app/engine/tool_executor.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/routers/chat.py`
- Test: `backend/tests/test_tool_executor.py`

**Why:** `db=None` in Task 11 is a footgun. Internal handlers need a real `AsyncSession`. Wire `db` through `ChatService.send` → `ToolExecutor.execute` from the FastAPI `Depends(get_db)` chain in the chat router.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_tool_executor.py`:

```python
async def test_handler_receives_db_session_when_provided():
    from pathlib import Path
    from unittest.mock import MagicMock

    from app.engine.base import ToolCall
    from app.engine.tool_executor import ToolExecutor
    from app.plugins.core.loader import LoadedPlugin
    from app.plugins.core.registry import PluginRegistry
    from app.plugins.core.schema import PluginManifest, ToolDef, ToolInputSchema

    captured = {}

    async def handler(args, user=None, db=None):
        captured["db"] = db
        return {"ok": True}

    tool = ToolDef(
        name="hello_db", description="d", input_schema=ToolInputSchema(), handler=handler,
    )
    manifest = PluginManifest(
        name="_hello", version="1", description="d", skills=[], type="internal",
    )
    plugin = LoadedPlugin(manifest=manifest, plugin_dir=Path("."), tools=[tool])

    registry = PluginRegistry(plugins_dir=Path("."))
    registry.register(plugin)

    fake_session = MagicMock(name="AsyncSession")
    executor = ToolExecutor(registry=registry)
    await executor.execute(
        ToolCall(id="tc1", name="hello_db", arguments={}),
        user=None,
        db=fake_session,
    )

    assert captured["db"] is fake_session
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tool_executor.py::test_handler_receives_db_session_when_provided -v`
Expected: FAIL — `ToolExecutor.execute` has no `db` parameter yet.

- [ ] **Step 3: Add `db` parameter to executor**

Edit `backend/app/engine/tool_executor.py`. Change the execute signature:

```python
    async def execute(
        self,
        call: ToolCall,
        user: "User | None" = None,
        db: "AsyncSession | None" = None,
    ) -> ToolResult:
```

Add the import at the top:

```python
from sqlalchemy.ext.asyncio import AsyncSession
```

Update the handler dispatch to pass `db`:

```python
            try:
                payload = await tool.handler(call.arguments, user=user, db=db)
```

- [ ] **Step 4: Thread `db` through `ChatService.send`**

Edit `backend/app/services/chat_service.py`. Add `db` parameter to `send`:

```python
    async def send(
        self,
        conversation: list[ChatMessage],
        user: User | None = None,
        db: "AsyncSession | None" = None,
    ) -> ChatReply:
```

Add the import near the top:

```python
from sqlalchemy.ext.asyncio import AsyncSession
```

Inside `send`, change the `tool_executor.execute` call to pass `db`:

```python
                result = await self.tool_executor.execute(call, user=user, db=db)
```

- [ ] **Step 5: Thread `db` through the chat router**

Find the chat router handler. Run: `cd backend && grep -n "chat_service.send\|get_chat_service" app/routers/chat.py`.

Edit `backend/app/routers/chat.py`. Locate the `send` endpoint and add `db: AsyncSession = Depends(get_db)` to its dependencies, then pass it:

```python
    reply = await chat_service.send(conversation, user=user, db=db)
```

Add imports at the top of `backend/app/routers/chat.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
```

- [ ] **Step 6: Run tests**

Run: `cd backend && pytest tests/test_tool_executor.py tests/test_chat_service.py tests/test_chat_router.py -v`
Expected: PASS. If `test_chat_service.py` calls `send` without passing `db`, the default `None` keeps old tests green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/engine/tool_executor.py backend/app/services/chat_service.py backend/app/routers/chat.py backend/tests/test_tool_executor.py
git commit -m "feat(executor): thread AsyncSession through chat to internal handlers"
```

---

### Task 13: Internal-dispatch branch in `/api/plugins/{name}/call`

**Files:**
- Modify: `backend/app/routers/plugins.py`
- Test: `backend/tests/test_plugins_router.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_plugins_router.py`:

```python
from pathlib import Path

import pytest
from fastapi import APIRouter

from app.dependencies import get_registry, reset_registry_for_tests
from app.plugins.core.loader import LoadedPlugin
from app.plugins.core.schema import PluginManifest
from app.plugins.core.types import PluginRegistration


@pytest.fixture
async def registered_internal_plugin():
    reset_registry_for_tests()
    registry = get_registry()

    router = APIRouter()

    @router.post("/echo")
    async def echo(body: dict):
        return {"echoed": body}

    manifest = PluginManifest(
        name="dispatch_demo", version="1", description="d", skills=[], type="internal",
    )
    loaded = LoadedPlugin(manifest=manifest, plugin_dir=Path("."), tools=[])
    loaded.registration = PluginRegistration(  # type: ignore[attr-defined]
        name="dispatch_demo", version="1", type="internal", router=router,
    )
    registry.register(loaded)
    yield
    registry.unregister("dispatch_demo")
    reset_registry_for_tests()


async def test_plugin_call_dispatches_internally(client, registered_internal_plugin):
    resp = await client.post(
        "/api/plugins/dispatch_demo/call",
        json={"method": "POST", "path": "/echo", "body": {"hello": "world"}},
    )
    assert resp.status_code == 200
    assert resp.json() == {"echoed": {"hello": "world"}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugins_router.py -v`
Expected: FAIL — current proxy attempts httpx on `plugin.manifest.api`, which is None for internal plugins, so it returns 400.

- [ ] **Step 3: Add internal-dispatch branch to the proxy**

Edit `backend/app/routers/plugins.py`. At the top of `call_plugin_api`, after the `plugin is None` check and BEFORE the `plugin.manifest.api is None` check, add:

```python
    # Phase 3: internal plugins are dispatched via their in-process router
    # rather than httpx. Look up the route on the plugin's registration
    # that matches (method, path) and invoke it directly.
    if plugin.manifest.type == "internal":
        return await _dispatch_internal(plugin, req, user)
```

Then append this helper function at the bottom of the file:

```python
from fastapi.routing import APIRoute
from starlette.routing import Match


async def _dispatch_internal(
    plugin, req: "PluginCallRequest", user: "User | None"
) -> Response:
    """Dispatch a proxy call to an internal plugin by invoking the
    matching APIRoute on its registration.router directly.

    This preserves the mobile PluginBridge interface (POST to
    /api/plugins/{name}/call with method/path/body) while avoiding a
    real HTTP round-trip. Auth uses JAIN's normal get_current_user
    chain from the outer router, and `user` is forwarded via a scope
    attribute the internal route can read if it wants.
    """
    registration = getattr(plugin, "registration", None)
    if registration is None or registration.router is None:
        raise HTTPException(
            status_code=500,
            detail=f"internal plugin '{plugin.manifest.name}' has no router",
        )

    method = req.method.upper()
    path = req.path

    # Find a matching APIRoute on the plugin's router.
    for route in registration.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if method not in route.methods:
            continue
        scope = {"type": "http", "method": method, "path": path, "headers": []}
        match, _child_scope = route.matches(scope)
        if match == Match.FULL:
            # Invoke the endpoint function directly. We build a synthetic
            # request body from req.body and let FastAPI's Pydantic layer
            # parse it through the route's dependant.
            try:
                if method == "GET":
                    result = await route.endpoint()  # no body
                else:
                    # Naive direct call: pass req.body if it's a dict and
                    # the endpoint expects a single body arg. For anything
                    # more complex, internal plugins can declare a pydantic
                    # model and we'll rely on this same dispatch path in
                    # Stage 3 with an explicit body forwarder.
                    result = await route.endpoint(req.body or {})
            except HTTPException as e:
                return Response(
                    content=f'{{"detail":"{e.detail}"}}',
                    status_code=e.status_code,
                    media_type="application/json",
                )
            import json as _json
            return Response(
                content=_json.dumps(result) if not isinstance(result, (bytes, str)) else result,
                status_code=200,
                media_type="application/json",
            )

    raise HTTPException(
        status_code=404,
        detail=f"no route for {method} {path} on plugin '{plugin.manifest.name}'",
    )
```

Note the limitation: this naive dispatcher only handles a single body arg. Stage 3 Task 24 upgrades it to build a proper ASGI `Request` for routes that use `Depends(get_db)` and `Depends(get_current_user)`.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_plugins_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/plugins.py backend/tests/test_plugins_router.py
git commit -m "feat(proxy): dispatch /api/plugins/{name}/call internally for internal plugins"
```

---

### Task 14: `_hello` throwaway internal plugin with end-to-end test

**Files:**
- Create: `backend/app/plugins/_hello/__init__.py`
- Create: `backend/app/plugins/_hello/plugin.json`
- Test: `backend/tests/test_hello_plugin.py`

- [ ] **Step 1: Write the failing end-to-end test**

Create `backend/tests/test_hello_plugin.py`:

```python
import json
from pathlib import Path

from app.engine.base import ToolCall
from app.engine.tool_executor import ToolExecutor
from app.plugins.core.loaders import InternalPluginLoader
from app.plugins.core.registry import PluginRegistry


async def test_hello_plugin_end_to_end():
    """Loader discovers _hello, registry has it, tool executor dispatches
    the handler, result is the expected greeting."""
    registry = PluginRegistry(
        plugins_dir=Path(__file__).parent.parent / "app" / "plugins",
    )
    InternalPluginLoader(
        plugins_dir=Path(__file__).parent.parent / "app" / "plugins",
    ).load_all(registry)

    assert registry.get_plugin("_hello") is not None

    _, tool = registry.find_tool("hello_world")
    assert tool is not None
    assert tool.handler is not None

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="hello_world", arguments={"who": "jim"}),
        user=None,
    )
    payload = json.loads(result.content)
    assert payload == {"greeting": "hi, jim"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_hello_plugin.py -v`
Expected: FAIL — plugin doesn't exist yet.

- [ ] **Step 3: Create the plugin package**

Create `backend/app/plugins/_hello/__init__.py`:

```python
"""Throwaway internal plugin proving the Stage 2 scaffolding.

Gets deleted at the end of Stage 2. Do not build on this.
"""

from app.plugins.core.schema import ToolDef, ToolInputSchema
from app.plugins.core.types import PluginRegistration


async def _hello_handler(args, user=None, db=None):
    who = args.get("who", "world")
    return {"greeting": f"hi, {who}"}


def register() -> PluginRegistration:
    return PluginRegistration(
        name="_hello",
        version="0.0.1",
        type="internal",
        tools=[
            ToolDef(
                name="hello_world",
                description="Say hi to someone.",
                input_schema=ToolInputSchema(
                    properties={"who": {"type": "string"}},
                    required=[],
                ),
                handler=_hello_handler,
            ),
        ],
    )
```

Create `backend/app/plugins/_hello/plugin.json`:

```json
{
  "name": "_hello",
  "version": "0.0.1",
  "description": "Throwaway internal plugin for Stage 2 validation",
  "type": "internal",
  "skills": [
    {
      "name": "greet",
      "description": "Say hi to someone.",
      "tools": ["hello_world"]
    }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_hello_plugin.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && pytest -x`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/plugins/_hello/ backend/tests/test_hello_plugin.py
git commit -m "test(plugins): add _hello throwaway internal plugin end-to-end"
```

---

### Task 15: Delete `_hello` at the end of Stage 2

**Files:**
- Delete: `backend/app/plugins/_hello/`
- Delete: `backend/tests/test_hello_plugin.py`

- [ ] **Step 1: Remove the plugin and its test**

```bash
rm -rf backend/app/plugins/_hello
rm backend/tests/test_hello_plugin.py
```

- [ ] **Step 2: Run suite to confirm nothing depended on it**

Run: `cd backend && pytest -x`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add -u backend/app/plugins backend/tests/test_hello_plugin.py
git commit -m "chore(plugins): remove _hello scaffolding plugin"
```

---

## Stage 3: Yardsailing clean rewrite as internal plugin

### Task 16: Create yardsailing package skeleton + plugin.json

**Files:**
- Create: `backend/app/plugins/yardsailing/__init__.py`
- Create: `backend/app/plugins/yardsailing/plugin.json`

- [ ] **Step 1: Create the package directory and stub __init__.py**

Create `backend/app/plugins/yardsailing/__init__.py`:

```python
"""First-party internal yardsailing plugin.

Ships as part of the JAIN deployment. Shares JAIN's DB session and trust
boundary. Models live in `models.py`, HTTP routes in `routes.py`, business
logic in `services.py`, LLM tool definitions in `tools.py`.
"""

from app.plugins.core.types import PluginRegistration

from .routes import router
from .tools import TOOLS


def register() -> PluginRegistration:
    return PluginRegistration(
        name="yardsailing",
        version="1.0.0",
        type="internal",
        router=router,
        tools=TOOLS,
        ui_bundle_path="bundle/yardsailing.js",
        ui_components=["SaleForm"],
    )
```

Create `backend/app/plugins/yardsailing/plugin.json`:

```json
{
  "name": "yardsailing",
  "version": "1.0.0",
  "description": "Find, create, and manage yard sales",
  "author": "jim shelly",
  "type": "internal",
  "skills": [
    {
      "name": "create-sale",
      "description": "Help user create a yard sale listing. Gather info conversationally or present a form.",
      "tools": ["create_yard_sale", "show_sale_form"],
      "components": ["SaleForm"]
    }
  ],
  "components": {
    "bundle": "bundle/yardsailing.js",
    "exports": ["SaleForm"]
  }
}
```

- [ ] **Step 2: No test yet — the package imports will fail until models/routes/tools exist. Skip verification; next tasks fill them in.**

- [ ] **Step 3: Commit**

```bash
git add backend/app/plugins/yardsailing/__init__.py backend/app/plugins/yardsailing/plugin.json
git commit -m "feat(yardsailing): scaffold internal plugin package"
```

---

### Task 17: `Sale` model

**Files:**
- Create: `backend/app/plugins/yardsailing/models.py`
- Test: `backend/tests/plugins/yardsailing/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/plugins/__init__.py` (empty file for the test package).
Create `backend/tests/plugins/yardsailing/__init__.py` (empty).

Create `backend/tests/plugins/yardsailing/test_models.py`:

```python
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_sale_model_persist_and_load(session):
    user = User(
        id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
    )
    session.add(user)
    await session.flush()

    sale = Sale(
        owner_id=user.id,
        title="Big Saturday",
        address="123 Main",
        description="stuff",
        start_date="2026-04-18",
        end_date="2026-04-18",
        start_time="08:00",
        end_time="14:00",
    )
    session.add(sale)
    await session.commit()

    got = await session.get(Sale, sale.id)
    assert got is not None
    assert got.title == "Big Saturday"
    assert got.owner_id == user.id
    assert isinstance(got.created_at, datetime)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/plugins/yardsailing/test_models.py -v`
Expected: FAIL on `ModuleNotFoundError: app.plugins.yardsailing.models`.

- [ ] **Step 3: Write the model**

Create `backend/app/plugins/yardsailing/models.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


def _sale_id() -> str:
    return str(uuid4())


class Sale(Base):
    """A yard sale listing owned by a JAIN user.

    Table is prefixed with `yardsailing_` per the internal-plugin naming
    convention so plugin tables can't collide with JAIN core tables.
    """

    __tablename__ = "yardsailing_sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_sale_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    owner: Mapped[User] = relationship()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/plugins/yardsailing/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/models.py backend/tests/plugins/__init__.py backend/tests/plugins/yardsailing/__init__.py backend/tests/plugins/yardsailing/test_models.py
git commit -m "feat(yardsailing): add Sale model with users FK"
```

---

### Task 18: `services.py` — create/list/get business logic

**Files:**
- Create: `backend/app/plugins/yardsailing/services.py`
- Test: `backend/tests/plugins/yardsailing/test_services.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/plugins/yardsailing/test_services.py`:

```python
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.services import (
    CreateSaleInput,
    create_sale,
    get_sale_by_id,
    list_sales_for_owner,
)


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        yield s, user
    await engine.dispose()


async def test_create_sale_persists_row(session_and_user):
    session, user = session_and_user
    data = CreateSaleInput(
        title="Big Sale", address="123 Main", description=None,
        start_date="2026-04-18", end_date=None,
        start_time="08:00", end_time="14:00",
    )
    sale = await create_sale(session, user, data)

    assert sale.id
    assert sale.owner_id == user.id
    assert sale.title == "Big Sale"


async def test_list_sales_for_owner_returns_only_this_users(session_and_user):
    session, user = session_and_user
    other = User(
        id=uuid4(), email="b@b.com", name="B", email_verified=True, google_sub="g2",
    )
    session.add(other)
    await session.commit()

    await create_sale(session, user, CreateSaleInput(
        title="Mine", address="a", description=None,
        start_date="2026-04-18", end_date=None,
        start_time="08:00", end_time="14:00",
    ))
    await create_sale(session, other, CreateSaleInput(
        title="Theirs", address="b", description=None,
        start_date="2026-04-18", end_date=None,
        start_time="08:00", end_time="14:00",
    ))

    rows = await list_sales_for_owner(session, user)
    assert len(rows) == 1
    assert rows[0].title == "Mine"


async def test_get_sale_by_id_returns_none_when_missing(session_and_user):
    session, _ = session_and_user
    assert await get_sale_by_id(session, "does-not-exist") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/plugins/yardsailing/test_services.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement services**

Create `backend/app/plugins/yardsailing/services.py`:

```python
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .models import Sale


@dataclass
class CreateSaleInput:
    title: str
    address: str
    description: str | None
    start_date: str
    end_date: str | None
    start_time: str
    end_time: str


async def create_sale(db: AsyncSession, user: User, data: CreateSaleInput) -> Sale:
    """Persist a new sale owned by `user`."""
    sale = Sale(
        owner_id=user.id,
        title=data.title,
        address=data.address,
        description=data.description,
        start_date=data.start_date,
        end_date=data.end_date,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    db.add(sale)
    await db.commit()
    await db.refresh(sale)
    return sale


async def list_sales_for_owner(db: AsyncSession, user: User) -> list[Sale]:
    """All sales owned by `user`, most recent first."""
    result = await db.execute(
        select(Sale).where(Sale.owner_id == user.id).order_by(Sale.created_at.desc()),
    )
    return list(result.scalars().all())


async def get_sale_by_id(db: AsyncSession, sale_id: str) -> Sale | None:
    return await db.get(Sale, sale_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/plugins/yardsailing/test_services.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/services.py backend/tests/plugins/yardsailing/test_services.py
git commit -m "feat(yardsailing): create_sale / list_sales_for_owner / get_sale_by_id services"
```

---

### Task 19: `routes.py` — APIRouter with create/list/get endpoints

**Files:**
- Create: `backend/app/plugins/yardsailing/routes.py`
- Test: `backend/tests/plugins/yardsailing/test_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/plugins/yardsailing/test_routes.py`:

```python
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def app_and_token():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = create_access_token(str(user.id))

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token


async def test_post_sales_requires_auth(app_and_token):
    client, _ = app_and_token
    resp = await client.post("/api/plugins/yardsailing/sales", json={
        "title": "s", "address": "a",
        "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
    })
    assert resp.status_code == 401


async def test_post_sales_creates_row(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Big Sale", "address": "123 Main",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Big Sale"
    assert "id" in body


async def test_get_my_sales_lists_own_rows(app_and_token):
    client, token = app_and_token
    await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "One", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        "/api/plugins/yardsailing/sales",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["title"] == "One"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/plugins/yardsailing/test_routes.py -v`
Expected: FAIL — routes module doesn't exist AND yardsailing isn't mounted yet.

- [ ] **Step 3: Create routes module**

Create `backend/app/plugins/yardsailing/routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

from .services import (
    CreateSaleInput,
    create_sale,
    get_sale_by_id,
    list_sales_for_owner,
)


router = APIRouter(prefix="/api/plugins/yardsailing", tags=["yardsailing"])


class CreateSaleBody(BaseModel):
    title: str
    address: str
    description: str | None = None
    start_date: str
    end_date: str | None = None
    start_time: str
    end_time: str


class SaleResponse(BaseModel):
    id: str
    title: str
    address: str
    description: str | None
    start_date: str
    end_date: str | None
    start_time: str
    end_time: str

    @classmethod
    def from_model(cls, sale) -> "SaleResponse":
        return cls(
            id=sale.id,
            title=sale.title,
            address=sale.address,
            description=sale.description,
            start_date=sale.start_date,
            end_date=sale.end_date,
            start_time=sale.start_time,
            end_time=sale.end_time,
        )


@router.post("/sales", status_code=status.HTTP_201_CREATED, response_model=SaleResponse)
async def create_sale_route(
    body: CreateSaleBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    sale = await create_sale(
        db, user,
        CreateSaleInput(
            title=body.title,
            address=body.address,
            description=body.description,
            start_date=body.start_date,
            end_date=body.end_date,
            start_time=body.start_time,
            end_time=body.end_time,
        ),
    )
    return SaleResponse.from_model(sale)


@router.get("/sales", response_model=list[SaleResponse])
async def list_my_sales_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SaleResponse]:
    sales = await list_sales_for_owner(db, user)
    return [SaleResponse.from_model(s) for s in sales]


@router.get("/sales/{sale_id}", response_model=SaleResponse)
async def get_sale_route(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale not found")
    return SaleResponse.from_model(sale)
```

- [ ] **Step 4: Mount the router**

The router gets mounted by the internal plugin loader automatically when Stage 2 machinery registers the plugin. Verify by adding to `create_app` an explicit `include_router` walk over all registered internal plugins. Edit `backend/app/main.py`:

Replace:

```python
from .routers import auth, chat, health, plugins
from .routers import settings as settings_router
```

with:

```python
from .dependencies import get_registry
from .routers import auth, chat, health, plugins
from .routers import settings as settings_router
```

Inside `create_app`, after the existing `app.include_router` calls, add:

```python
    # Phase 3: mount internal plugin routers. get_registry() loads both
    # internal and external plugins (external are HTTP, so they have no
    # router to mount — we skip them). Each internal plugin's router has
    # its own /api/plugins/<name>/... prefix baked in.
    registry = get_registry()
    for plugin in registry.list_plugins():
        if plugin.type != "internal":
            continue
        loaded = registry.get_plugin(plugin.name)
        registration = getattr(loaded, "registration", None)
        if registration is None or registration.router is None:
            continue
        app.include_router(registration.router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/plugins/yardsailing/test_routes.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/plugins/yardsailing/routes.py backend/app/main.py backend/tests/plugins/yardsailing/test_routes.py
git commit -m "feat(yardsailing): add HTTP routes and mount internal plugin routers"
```

---

### Task 20: `tools.py` — LLM tool definitions with handler

**Files:**
- Create: `backend/app/plugins/yardsailing/tools.py`
- Test: `backend/tests/plugins/yardsailing/test_tools.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/plugins/yardsailing/test_tools.py`:

```python
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale
from app.plugins.yardsailing.tools import (
    TOOLS,
    create_yard_sale_handler,
)


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        yield s, user
    await engine.dispose()


def test_tools_list_has_both_tools():
    names = {t.name for t in TOOLS}
    assert names == {"create_yard_sale", "show_sale_form"}


def test_show_sale_form_is_ui_component():
    t = next(t for t in TOOLS if t.name == "show_sale_form")
    assert t.ui_component == "SaleForm"
    assert t.handler is None


def test_create_yard_sale_requires_auth():
    t = next(t for t in TOOLS if t.name == "create_yard_sale")
    assert t.auth_required is True
    assert t.handler is not None


async def test_create_yard_sale_handler_creates_row(session_and_user):
    session, user = session_and_user
    result = await create_yard_sale_handler(
        {
            "title": "Weekend Sale", "address": "100 Oak",
            "start_date": "2026-04-18", "start_time": "09:00", "end_time": "15:00",
        },
        user=user,
        db=session,
    )
    assert result["ok"] is True
    assert "id" in result

    from sqlalchemy import select
    rows = (await session.execute(select(Sale))).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "Weekend Sale"


async def test_create_yard_sale_handler_rejects_missing_user(session_and_user):
    session, _ = session_and_user
    result = await create_yard_sale_handler(
        {"title": "x", "address": "y",
         "start_date": "2026-04-18", "start_time": "09:00", "end_time": "15:00"},
        user=None,
        db=session,
    )
    assert result["error"] == "auth_required"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/plugins/yardsailing/test_tools.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement tools**

Create `backend/app/plugins/yardsailing/tools.py`:

```python
from typing import Any

from app.plugins.core.schema import ToolDef, ToolInputSchema

from .services import CreateSaleInput, create_sale


_CREATE_INPUT_SCHEMA = ToolInputSchema(
    type="object",
    properties={
        "title": {"type": "string"},
        "description": {"type": "string"},
        "address": {"type": "string"},
        "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
        "start_time": {"type": "string", "description": "HH:MM 24-hour"},
        "end_time": {"type": "string", "description": "HH:MM 24-hour"},
    },
    required=["title", "address", "start_date", "start_time", "end_time"],
)

_SHOW_FORM_INPUT_SCHEMA = ToolInputSchema(
    type="object",
    properties={
        "title": {"type": "string", "description": "Pre-filled sale title (optional)"},
        "description": {"type": "string", "description": "Pre-filled description (optional)"},
        "address": {"type": "string", "description": "Pre-filled address (optional)"},
        "start_date": {"type": "string", "description": "Pre-filled start date YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "Pre-filled end date YYYY-MM-DD"},
        "start_time": {"type": "string", "description": "Pre-filled start time HH:MM"},
        "end_time": {"type": "string", "description": "Pre-filled end time HH:MM"},
    },
    required=[],
)


async def create_yard_sale_handler(
    args: dict[str, Any], user=None, db=None,
) -> dict[str, Any]:
    """Tool handler that wraps the service-layer create_sale.

    Returns a shape the chat service treats as a successful non-UI result:
    {"ok": True, "id": "...", "title": "..."} on success, or
    {"error": "..."} on failure.
    """
    if user is None:
        return {"error": "auth_required"}
    if db is None:
        return {"error": "no db session"}

    try:
        sale = await create_sale(
            db, user,
            CreateSaleInput(
                title=args["title"],
                address=args["address"],
                description=args.get("description"),
                start_date=args["start_date"],
                end_date=args.get("end_date"),
                start_time=args["start_time"],
                end_time=args["end_time"],
            ),
        )
    except KeyError as e:
        return {"error": f"missing field: {e.args[0]}"}

    return {"ok": True, "id": sale.id, "title": sale.title}


TOOLS = [
    ToolDef(
        name="create_yard_sale",
        description=(
            "Create a new yard sale listing. Use this when the user has given "
            "you all the sale details conversationally and confirmed they want "
            "to submit."
        ),
        input_schema=_CREATE_INPUT_SCHEMA,
        auth_required=True,
        handler=create_yard_sale_handler,
    ),
    ToolDef(
        name="show_sale_form",
        description=(
            "Display the yard sale creation form for the user to fill in "
            "manually. Use this when the user explicitly asks for a form, or "
            "when they have given you a lot of sale info at once that you "
            "want to pre-fill into a form rather than asking question by "
            "question. Pass any fields you've already extracted as arguments "
            "— they will pre-fill the form."
        ),
        input_schema=_SHOW_FORM_INPUT_SCHEMA,
        ui_component="SaleForm",
    ),
]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/plugins/yardsailing/test_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/tools.py backend/tests/plugins/yardsailing/test_tools.py
git commit -m "feat(yardsailing): add create_yard_sale and show_sale_form ToolDefs"
```

---

### Task 21: Copy `SaleForm.tsx` into plugin package

**Files:**
- Create: `backend/app/plugins/yardsailing/components/SaleForm.tsx`

- [ ] **Step 1: Copy the file**

```bash
mkdir -p backend/app/plugins/yardsailing/components
cp C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/src/SaleForm.tsx backend/app/plugins/yardsailing/components/SaleForm.tsx
```

- [ ] **Step 2: Update the API call path**

The old form POSTs to `/api/sales` (external convention). The new internal routes live at `/api/plugins/yardsailing/sales`, BUT the mobile PluginBridge wraps calls in `/api/plugins/{pluginName}/call` with body `{method, path, body}` where `path` is joined with the plugin's own prefix. For internal dispatch in Task 13, we pass `path` directly to the internal router lookup.

Edit `backend/app/plugins/yardsailing/components/SaleForm.tsx`. Change the line:

```tsx
      const result = await bridge.callPluginApi("/api/sales", "POST", data);
```

to:

```tsx
      const result = await bridge.callPluginApi("/api/plugins/yardsailing/sales", "POST", data);
```

- [ ] **Step 3: Add an index entry point for esbuild**

Create `backend/app/plugins/yardsailing/components/index.ts`:

```ts
export { SaleForm } from "./SaleForm";
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/plugins/yardsailing/components/
git commit -m "feat(yardsailing): copy SaleForm component into plugin package"
```

---

### Task 22: Build UI bundle with esbuild

**Files:**
- Create: `backend/app/plugins/yardsailing/build.mjs`
- Create: `backend/app/plugins/yardsailing/package.json`
- Create: `backend/app/plugins/yardsailing/bundle/yardsailing.js` (generated, committed)

- [ ] **Step 1: Create package.json with esbuild devDep**

Create `backend/app/plugins/yardsailing/package.json`:

```json
{
  "name": "jain-yardsailing-bundle",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node build.mjs"
  },
  "devDependencies": {
    "esbuild": "^0.24.0"
  }
}
```

- [ ] **Step 2: Create build script adapted from jain-plugins/tools/build.ts**

Create `backend/app/plugins/yardsailing/build.mjs`:

```js
import { build } from "esbuild";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, mkdirSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname);

const entry = join(ROOT, "components", "index.ts");
const outfile = join(ROOT, "bundle", "yardsailing.js");
const outdir = dirname(outfile);
if (!existsSync(outdir)) mkdirSync(outdir, { recursive: true });

await build({
  entryPoints: [entry],
  bundle: true,
  outfile,
  format: "iife",
  platform: "neutral",
  target: "es2020",
  jsx: "transform",
  external: ["react", "react-native"],
  loader: { ".tsx": "tsx", ".ts": "ts" },
  logLevel: "info",
});

console.log(`[yardsailing] built ${outfile}`);
```

- [ ] **Step 3: Install deps and build**

```bash
cd backend/app/plugins/yardsailing && npm install && npm run build
```

Expected: `bundle/yardsailing.js` is created (a file of ~5-50 kB).

- [ ] **Step 4: Verify the bundle loads via the existing bundle endpoint**

Start JAIN: `cd backend && uvicorn app.main:app --port 8000` (briefly).
Hit `curl http://localhost:8000/api/plugins/yardsailing/bundle` — expect the bundled JS (not 404). Ctrl+C to stop.

- [ ] **Step 5: Commit bundle and build config**

```bash
git add backend/app/plugins/yardsailing/build.mjs backend/app/plugins/yardsailing/package.json backend/app/plugins/yardsailing/bundle/yardsailing.js
# Add .gitignore rule for node_modules inside the plugin
echo "backend/app/plugins/yardsailing/node_modules/" >> .gitignore
git add .gitignore
git commit -m "build(yardsailing): esbuild config and initial UI bundle"
```

---

### Task 23: Ensure `yardsailing_sales` table is created at startup

**Files:**
- Modify: `backend/app/database.py`

- [ ] **Step 1: Verify autopickup**

Because `app/plugins/yardsailing/models.py` imports `Base` from `app.models.base`, the model registers on `Base.metadata` AS LONG AS the module is imported before `init_db` runs `create_all`. The internal plugin loader imports the package during `get_registry()`, which happens at `_registry_singleton` cache time. Call order:

1. `main.create_app` runs at import time.
2. `include_router` for the plugin is inside `create_app`, AFTER `get_registry()` — so the plugin package imports before the FastAPI app is returned.
3. `init_db` runs inside `lifespan`, AFTER `create_app` returns — so the model is already on `Base.metadata`.

Run: `cd backend && python -c "
import asyncio
from app.main import create_app
from app.database import engine
from app.models.base import Base
app = create_app()
print([t.name for t in Base.metadata.tables.values() if 'yardsailing' in t.name])
"`

Expected: `['yardsailing_sales']`.

- [ ] **Step 2: If the print shows empty, force-import in database.py**

Only if Step 1 prints nothing — edit `backend/app/database.py` to add at the top of `init_db`:

```python
async def init_db() -> None:
    # Import all plugin model modules so their tables register on Base
    # before create_all runs. Currently only yardsailing; future internal
    # plugins should add themselves here or be discovered by the loader.
    import app.plugins.yardsailing.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 3: Run the full suite**

Run: `cd backend && pytest -x`
Expected: PASS.

- [ ] **Step 4: Commit only if database.py was modified**

```bash
git add backend/app/database.py
git commit -m "chore(db): force-import yardsailing models before create_all"
```

---

### Task 24: Upgrade internal-dispatch proxy to honor FastAPI deps

**Files:**
- Modify: `backend/app/routers/plugins.py`
- Test: `backend/tests/test_plugins_router.py`

**Context:** Task 13's dispatcher is naive — it calls `route.endpoint(req.body)` directly, bypassing FastAPI's `Depends(get_current_user)`/`Depends(get_db)` resolution. The yardsailing route needs those. Replace the naive call with a synthetic ASGI request dispatched through FastAPI's real routing.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_plugins_router.py`:

```python
async def test_plugin_call_dispatches_internal_with_auth(app_and_token_for_yardsailing):
    client, token = app_and_token_for_yardsailing
    resp = await client.post(
        "/api/plugins/yardsailing/call",
        json={
            "method": "POST", "path": "/api/plugins/yardsailing/sales",
            "body": {
                "title": "Via Proxy", "address": "1 A",
                "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
                "description": None, "end_date": None,
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Via Proxy"
```

Add the fixture at the top of `test_plugins_router.py`:

```python
import pytest
from uuid import uuid4
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def app_and_token_for_yardsailing():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = create_access_token(str(user.id))

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugins_router.py::test_plugin_call_dispatches_internal_with_auth -v`
Expected: FAIL — the naive dispatcher can't resolve `Depends(get_current_user)`.

- [ ] **Step 3: Replace `_dispatch_internal` with a request-forwarding implementation**

Edit `backend/app/routers/plugins.py`. Replace the entire `_dispatch_internal` helper from Task 13 with an implementation that forwards to the FastAPI app itself over an in-memory ASGI transport. This sidesteps re-implementing FastAPI's dependency injection machinery.

Add at the top:

```python
from fastapi import Request
```

Replace `_dispatch_internal`:

```python
async def _dispatch_internal(
    plugin, req: "PluginCallRequest", request: Request,
) -> Response:
    """Forward the proxy call to the plugin's own router via the same
    FastAPI app instance. We construct an ASGI sub-request that targets
    the plugin's path, reusing the original Authorization header so
    get_current_user resolves the same user.
    """
    import json as _json

    method = req.method.upper()
    path = req.path
    body_bytes = _json.dumps(req.body or {}).encode("utf-8")
    auth_header = request.headers.get("authorization", "")

    # Build a minimal ASGI scope for the sub-request.
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [
            (b"content-type", b"application/json"),
            (b"authorization", auth_header.encode("utf-8")) if auth_header else (b"x-empty", b""),
        ],
        "app": request.app,
    }

    sent: list[dict] = []
    started: dict = {}

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            started.update(message)
        elif message["type"] == "http.response.body":
            sent.append(message)

    await request.app(scope, receive, send)

    status_code = started.get("status", 500)
    body = b"".join(m.get("body", b"") for m in sent)
    return Response(
        content=body,
        status_code=status_code,
        media_type="application/json",
    )
```

Update the `call_plugin_api` signature to pass the `Request`:

```python
@router.post("/{plugin_name}/call")
async def call_plugin_api(
    plugin_name: str,
    req: PluginCallRequest,
    request: Request,
    registry: PluginRegistry = Depends(get_registry),
    user: User | None = Depends(get_current_user_optional),
) -> Response:
    plugin = registry.get_plugin(plugin_name)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"plugin '{plugin_name}' not found")

    if plugin.manifest.type == "internal":
        return await _dispatch_internal(plugin, req, request)

    if plugin.manifest.api is None:
        raise HTTPException(
            status_code=400, detail=f"plugin '{plugin_name}' has no api base_url"
        )

    # ... existing external proxy path unchanged ...
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_plugins_router.py -v`
Expected: PASS on both the simple dispatch test (which needs a minor tweak if the body parsing differs) AND the auth-required test.

If the first test breaks because its router has no `/api/plugins/dispatch_demo` prefix, update the fixture to use the plugin's full prefix path OR adjust the test's `path` field accordingly.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/plugins.py backend/tests/test_plugins_router.py
git commit -m "feat(proxy): dispatch internal plugin calls via ASGI sub-request"
```

---

### Task 25: End-to-end chat → form → DB row integration test

**Files:**
- Test: `backend/tests/plugins/yardsailing/test_integration.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/plugins/yardsailing/test_integration.py`:

```python
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.jwt import create_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale


@pytest.fixture
async def client_and_token():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = create_access_token(str(user.id))
        user_id = user.id

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token, user_id


async def test_form_submission_creates_sale_row(client_and_token):
    """Simulates: mobile SaleForm POSTs through PluginBridge →
    /api/plugins/yardsailing/call → internal dispatch → row persisted."""
    client, token, user_id = client_and_token

    resp = await client.post(
        "/api/plugins/yardsailing/call",
        json={
            "method": "POST",
            "path": "/api/plugins/yardsailing/sales",
            "body": {
                "title": "Garage Cleanout", "address": "500 Elm",
                "description": "Tools and furniture",
                "start_date": "2026-05-02", "end_date": "2026-05-02",
                "start_time": "07:00", "end_time": "13:00",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    async with async_session() as s:
        rows = (await s.execute(select(Sale))).scalars().all()
        assert len(rows) == 1
        assert rows[0].title == "Garage Cleanout"
        assert rows[0].owner_id == user_id


async def test_bundle_endpoint_serves_yardsailing_js(client_and_token):
    client, token, _ = client_and_token
    resp = await client.get("/api/plugins/yardsailing/bundle")
    assert resp.status_code == 200
    # The bundle was built by Task 22, so it should contain the compiled
    # SaleForm export identifier.
    assert "SaleForm" in resp.text
```

- [ ] **Step 2: Run tests**

Run: `cd backend && pytest tests/plugins/yardsailing/test_integration.py -v`
Expected: PASS (assuming Tasks 16-24 landed correctly and the bundle exists on disk from Task 22).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/plugins/yardsailing/test_integration.py
git commit -m "test(yardsailing): end-to-end form → proxy → DB integration"
```

---

### Task 26: Remove yardsailing from `jain-plugins` repo

**Files:**
- Delete: `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/`

- [ ] **Step 1: Verify JAIN still loads correctly without the external manifest**

Run: `cd backend && pytest -x`
Expected: PASS. (The `tests/fixtures/plugins/` fixture directory is a separate copy used only in tests and is NOT deleted.)

- [ ] **Step 2: Delete the directory in the jain-plugins repo**

```bash
cd C:/Users/jimsh/repos/jain-plugins
rm -rf plugins/yardsailing
```

- [ ] **Step 3: Commit in jain-plugins**

```bash
cd C:/Users/jimsh/repos/jain-plugins
git add -u plugins/
git commit -m "chore(yardsailing): remove external plugin — migrated to JAIN internal plugin"
```

- [ ] **Step 4: In JAIN, update PLUGINS_DIR check tolerance**

Because `PLUGINS_DIR` defaults to `../jain-plugins/plugins`, JAIN's external loader walks this directory and finds it empty (or finds only other plugins). Confirm the external loader handles an empty directory gracefully — Task 9 already does (`if not self.plugins_dir.exists(): return` and the iteration handles empties).

Run: `cd backend && uvicorn app.main:app --port 8000` briefly. Expect `[App] loaded plugins: ['yardsailing']` where `yardsailing` is now the INTERNAL one.

- [ ] **Step 5: No additional JAIN commit for this task (the deletion was in a separate repo).**

---

## Stage 4: External tier runtime install

### Task 27: Add `JAIN_ADMIN_EMAILS` setting and `get_current_admin_user`

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/auth/admin.py`
- Test: `backend/tests/test_admin_dep.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_admin_dep.py`:

```python
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth.admin import get_current_admin_user
from app.config import settings
from app.models.user import User


@pytest.fixture
def admin_user():
    return User(
        id=uuid4(), email="admin@example.com", name="Admin", email_verified=True, google_sub="g1",
    )


@pytest.fixture
def normal_user():
    return User(
        id=uuid4(), email="user@example.com", name="User", email_verified=True, google_sub="g2",
    )


def test_admin_emails_parsed_from_setting():
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com, other@example.com"
    try:
        assert settings.admin_emails == {"admin@example.com", "other@example.com"}
    finally:
        settings.JAIN_ADMIN_EMAILS = original


def test_admin_emails_case_insensitive():
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "Admin@Example.COM"
    try:
        assert "admin@example.com" in settings.admin_emails
    finally:
        settings.JAIN_ADMIN_EMAILS = original


def test_get_current_admin_user_allows_admin(admin_user):
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com"
    try:
        got = get_current_admin_user(user=admin_user)
        assert got is admin_user
    finally:
        settings.JAIN_ADMIN_EMAILS = original


def test_get_current_admin_user_rejects_non_admin(normal_user):
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com"
    try:
        with pytest.raises(HTTPException) as exc:
            get_current_admin_user(user=normal_user)
        assert exc.value.status_code == 403
    finally:
        settings.JAIN_ADMIN_EMAILS = original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_admin_dep.py -v`
Expected: FAIL — module and setting don't exist.

- [ ] **Step 3: Add the setting**

Edit `backend/app/config.py`. Add inside `Settings` class:

```python
    # Phase 3: comma-separated list of admin emails, for plugin install/uninstall.
    JAIN_ADMIN_EMAILS: str = ""

    @property
    def admin_emails(self) -> set[str]:
        return {
            e.strip().lower()
            for e in self.JAIN_ADMIN_EMAILS.split(",")
            if e.strip()
        }
```

- [ ] **Step 4: Create the admin dependency**

Create `backend/app/auth/admin.py`:

```python
from fastapi import Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.config import settings
from app.models.user import User


def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    """Require that the authenticated user's email is in JAIN_ADMIN_EMAILS.

    Raises 403 for non-admins, propagates 401 from get_current_user for
    anonymous callers.
    """
    if user.email.lower() not in settings.admin_emails:
        raise HTTPException(status_code=403, detail="admin only")
    return user
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_admin_dep.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/auth/admin.py backend/tests/test_admin_dep.py
git commit -m "feat(auth): add JAIN_ADMIN_EMAILS and get_current_admin_user dependency"
```

---

### Task 28: `ExternalPluginLoader.load_from_db` reads `installed_plugins`

**Files:**
- Modify: `backend/app/plugins/core/loaders.py`
- Test: `backend/tests/test_plugin_loaders.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_plugin_loaders.py`:

```python
async def test_external_loader_reads_installed_plugins_table():
    import json
    from datetime import datetime
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models.base import Base
    from app.models.installed_plugin import InstalledPlugin
    from app.models.user import User
    from app.plugins.core.loaders import ExternalPluginLoader
    from app.plugins.core.registry import PluginRegistry

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.flush()

        manifest = {
            "name": "weather",
            "version": "1.0.0",
            "type": "external",
            "description": "Weather lookup",
            "skills": [],
            "api": {"base_url": "https://weather.example.com"},
        }
        s.add(InstalledPlugin(
            name="weather",
            manifest_url="https://weather.example.com/plugin.json",
            manifest_json=json.dumps(manifest),
            service_key="sk-1",
            bundle_path=None,
            installed_at=datetime.utcnow(),
            installed_by=user.id,
        ))
        await s.commit()

    registry = PluginRegistry(plugins_dir="/tmp/unused")
    loader = ExternalPluginLoader(plugins_dir="/tmp/unused")

    async with maker() as s:
        await loader.load_from_db(registry, s)

    plugin = registry.get_plugin("weather")
    assert plugin is not None
    assert plugin.manifest.type == "external"
    assert plugin.manifest.api.base_url == "https://weather.example.com"

    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugin_loaders.py::test_external_loader_reads_installed_plugins_table -v`
Expected: FAIL — `load_from_db` doesn't exist.

- [ ] **Step 3: Implement `load_from_db`**

Edit `backend/app/plugins/core/loaders.py`. Append to `ExternalPluginLoader`:

```python
    async def load_from_db(self, registry: PluginRegistry, db) -> None:
        """Phase 3 Stage 4: load external plugins from the installed_plugins table.

        Each row's manifest_json is trusted because it was validated at install
        time. If a row fails to parse, skip it and log a warning.
        """
        from sqlalchemy import select

        from app.models.installed_plugin import InstalledPlugin

        result = await db.execute(select(InstalledPlugin))
        for row in result.scalars().all():
            try:
                manifest = PluginManifest.model_validate_json(row.manifest_json)
            except Exception as e:
                _log.warning(
                    "installed plugin '%s' has invalid manifest_json: %s", row.name, e,
                )
                continue

            from pathlib import Path as _Path
            loaded = LoadedPlugin(
                manifest=manifest,
                plugin_dir=_Path(row.bundle_path or "").parent if row.bundle_path else _Path("."),
            )
            # Stash the service key on the loaded plugin so the tool executor
            # can look it up per-plugin instead of reading settings.JAIN_SERVICE_KEY.
            loaded.service_key = row.service_key  # type: ignore[attr-defined]
            registry.register(loaded)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_plugin_loaders.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/core/loaders.py backend/tests/test_plugin_loaders.py
git commit -m "feat(plugins): ExternalPluginLoader.load_from_db for runtime-installed plugins"
```

---

### Task 29: Wire `load_from_db` into startup

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/dependencies.py`

- [ ] **Step 1: Switch external loader startup path**

The old Stage 1 code called `ExternalPluginLoader.load_all(registry)` which walked `PLUGINS_DIR`. Now that yardsailing is internal and there are no external plugins on disk, replace the filesystem walk with a DB read at lifespan-startup.

Edit `backend/app/dependencies.py`. Remove the `ExternalPluginLoader` invocation from `_registry_singleton`:

```python
@lru_cache(maxsize=1)
def _registry_singleton() -> PluginRegistry:
    reg = PluginRegistry(plugins_dir=settings.PLUGINS_DIR)
    internal_dir = Path(__file__).parent / "plugins"
    InternalPluginLoader(plugins_dir=internal_dir).load_all(reg)
    # External plugins are loaded from the installed_plugins table in the
    # FastAPI lifespan context (see main.lifespan) because it needs an
    # async DB session.
    return reg
```

Edit `backend/app/main.py`. Extend `lifespan`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Phase 3: load runtime-installed external plugins from the DB.
    from .database import async_session
    from .dependencies import get_registry
    from .plugins.core.loaders import ExternalPluginLoader

    registry = get_registry()
    loader = ExternalPluginLoader(plugins_dir=settings.PLUGINS_DIR)
    async with async_session() as db:
        await loader.load_from_db(registry, db)

    yield
```

- [ ] **Step 2: Run the existing tests**

Run: `cd backend && pytest -x`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/dependencies.py backend/app/main.py
git commit -m "feat(plugins): load external plugins from installed_plugins table at lifespan start"
```

---

### Task 30: `POST /api/plugins/install` endpoint

**Files:**
- Create: `backend/app/routers/plugins_admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_plugins_install.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_plugins_install.py`:

```python
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token
from app.config import settings
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.installed_plugin import InstalledPlugin
from app.models.user import User


@pytest.fixture
async def admin_client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as s:
        user = User(
            id=uuid4(), email="admin@example.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = create_access_token(str(user.id))

    orig = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com"
    app = create_app()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, token
    finally:
        settings.JAIN_ADMIN_EMAILS = orig


_VALID_MANIFEST = {
    "name": "weather",
    "version": "1.0.0",
    "type": "external",
    "description": "Weather lookup",
    "skills": [],
    "api": {"base_url": "https://weather.example.com"},
}


async def test_install_requires_admin_auth(admin_client):
    client, _ = admin_client
    resp = await client.post(
        "/api/plugins/install",
        json={"manifest_url": "https://weather.example.com/plugin.json", "service_key": "sk"},
    )
    assert resp.status_code == 401


async def test_install_fetches_validates_persists(admin_client):
    client, token = admin_client
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        instance = Mock.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_FakeResponse(200, _VALID_MANIFEST))
        resp = await client.post(
            "/api/plugins/install",
            json={
                "manifest_url": "https://weather.example.com/plugin.json",
                "service_key": "sk-1234",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "weather"

    async with async_session() as s:
        row = await s.get(InstalledPlugin, "weather")
        assert row is not None
        assert row.service_key == "sk-1234"
        assert json.loads(row.manifest_json)["name"] == "weather"


async def test_install_rejects_internal_type(admin_client):
    client, token = admin_client
    manifest = dict(_VALID_MANIFEST)
    manifest["type"] = "internal"
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(200, manifest),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
    assert "internal" in resp.json()["detail"].lower()


async def test_install_rejects_name_collision_with_internal(admin_client):
    client, token = admin_client
    manifest = dict(_VALID_MANIFEST)
    manifest["name"] = "yardsailing"
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(200, manifest),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 409


async def test_install_handles_manifest_fetch_failure(admin_client):
    client, token = admin_client
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(404, {"error": "nope"}),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                "err", request=None, response=httpx.Response(self.status_code),
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_plugins_install.py -v`
Expected: FAIL — router module doesn't exist.

- [ ] **Step 3: Create the install router**

Create `backend/app/routers/plugins_admin.py`:

```python
import json
import logging
from datetime import datetime
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

_MAX_BUNDLE_BYTES = 2 * 1024 * 1024  # 2 MiB
_VALID_JS_CONTENT_TYPES = {"application/javascript", "text/javascript"}
_BUNDLE_CACHE_DIR = Path("data/plugins")


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

    # 5. Tool name collision check
    existing_tool_names = {t.name for t in registry.all_tools()}
    incoming_tool_names = []
    for skill in manifest.skills:
        incoming_tool_names.extend(skill.tools)
    collisions = set(incoming_tool_names) & existing_tool_names
    if collisions:
        raise HTTPException(
            status_code=409,
            detail=f"tool name collision: {sorted(collisions)}",
        )

    # 6. Optional bundle fetch
    bundle_path: str | None = None
    if manifest.components is not None and manifest.components.bundle:
        bundle_path = await _fetch_and_cache_bundle(
            manifest.name, manifest.components.bundle,
        )

    # 7. Persist
    manifest_json = json.dumps(manifest.model_dump(mode="json"))
    row = InstalledPlugin(
        name=manifest.name,
        manifest_url=body.manifest_url,
        manifest_json=manifest_json,
        service_key=body.service_key,
        bundle_path=bundle_path,
        installed_at=datetime.utcnow(),
        installed_by=admin.id,
    )
    db.add(row)
    await db.commit()

    # 8. Register in memory
    loaded = LoadedPlugin(
        manifest=manifest,
        plugin_dir=Path(bundle_path).parent if bundle_path else Path("."),
    )
    loaded.service_key = body.service_key  # type: ignore[attr-defined]
    registry.register(loaded)

    return InstallResponse(
        name=manifest.name,
        version=manifest.version,
        tools=incoming_tool_names,
    )


async def _fetch_and_cache_bundle(plugin_name: str, bundle_url: str) -> str:
    """Fetch a plugin's UI bundle, validate content-type and size, cache to disk."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(bundle_url)
            resp.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"bundle fetch failed: {e}")

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in _VALID_JS_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"bundle content-type must be application/javascript, got {content_type}",
        )
    if len(resp.content) > _MAX_BUNDLE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"bundle too large ({len(resp.content)} > {_MAX_BUNDLE_BYTES})",
        )

    plugin_cache_dir = _BUNDLE_CACHE_DIR / plugin_name
    plugin_cache_dir.mkdir(parents=True, exist_ok=True)
    bundle_file = plugin_cache_dir / "bundle.js"
    bundle_file.write_bytes(resp.content)
    return str(bundle_file)
```

- [ ] **Step 4: Mount the router**

Edit `backend/app/main.py`. Add to the imports:

```python
from .routers import plugins_admin
```

Add to `create_app` after the existing `include_router` calls:

```python
    app.include_router(plugins_admin.router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_plugins_install.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/plugins_admin.py backend/app/main.py backend/tests/test_plugins_install.py
git commit -m "feat(plugins): POST /api/plugins/install for runtime external install"
```

---

### Task 31: `GET /api/plugins/installed` and `DELETE /api/plugins/{name}`

**Files:**
- Modify: `backend/app/routers/plugins_admin.py`
- Test: `backend/tests/test_plugins_install.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_plugins_install.py`:

```python
async def test_list_installed_returns_empty_initially(admin_client):
    client, token = admin_client
    resp = await client.get(
        "/api/plugins/installed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_installed_then_delete(admin_client):
    client, token = admin_client
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(200, _VALID_MANIFEST),
        )
        await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "sk"},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/api/plugins/installed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert [p["name"] for p in resp.json()] == ["weather"]

    resp = await client.delete(
        "/api/plugins/weather",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    async with async_session() as s:
        assert await s.get(InstalledPlugin, "weather") is None

    resp = await client.get(
        "/api/plugins/installed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json() == []


async def test_delete_unknown_plugin_returns_404(admin_client):
    client, token = admin_client
    resp = await client.delete(
        "/api/plugins/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_plugins_install.py::test_list_installed_returns_empty_initially -v`
Expected: FAIL (endpoint missing).

- [ ] **Step 3: Implement the endpoints**

Append to `backend/app/routers/plugins_admin.py`:

```python
from sqlalchemy import select


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

    # Delete cached bundle file if any
    if row.bundle_path:
        try:
            Path(row.bundle_path).unlink(missing_ok=True)
        except Exception as e:
            _log.warning("failed to delete bundle %s: %s", row.bundle_path, e)

    await db.delete(row)
    await db.commit()
    registry.unregister(plugin_name)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_plugins_install.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/plugins_admin.py backend/tests/test_plugins_install.py
git commit -m "feat(plugins): GET /installed and DELETE /{name} admin endpoints"
```

---

### Task 32: Per-plugin service key in tool executor + proxy

**Files:**
- Modify: `backend/app/engine/tool_executor.py`
- Modify: `backend/app/routers/plugins.py`
- Test: `backend/tests/test_tool_executor.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_tool_executor.py`:

```python
async def test_executor_uses_per_plugin_service_key(registry, httpx_mock):
    """When the plugin has a `service_key` attribute set (by the external
    loader), the executor forwards that instead of settings.JAIN_SERVICE_KEY."""
    from uuid import uuid4
    from app.config import settings
    from app.models.user import User

    plugin = registry.get_plugin("yardsailing")
    plugin.service_key = "per-plugin-key-xyz"  # type: ignore[attr-defined]

    original_key = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = "global-should-be-ignored"

    try:
        httpx_mock.add_response(
            method="GET",
            url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
            json={"sales": []},
        )
        executor = ToolExecutor(registry=registry)
        await executor.execute(
            ToolCall(
                id="tc1",
                name="find_yard_sales",
                arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
            ),
            user=User(
                id=uuid4(), email="a@b.com", name="A",
                email_verified=True, google_sub="g",
            ),
        )
        sent = httpx_mock.get_requests()[0]
        assert sent.headers["x-jain-service-key"] == "per-plugin-key-xyz"
    finally:
        settings.JAIN_SERVICE_KEY = original_key
        plugin.service_key = None  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tool_executor.py::test_executor_uses_per_plugin_service_key -v`
Expected: FAIL — executor still reads `settings.JAIN_SERVICE_KEY` unconditionally.

- [ ] **Step 3: Update the executor header-building block**

Edit `backend/app/engine/tool_executor.py`. Replace the header block in `execute`:

```python
        headers = {"X-Requested-With": "XMLHttpRequest"}
        plugin_service_key = getattr(plugin, "service_key", None) or settings.JAIN_SERVICE_KEY
        if user is not None and plugin_service_key:
            from urllib.parse import quote
            headers["X-Jain-Service-Key"] = plugin_service_key
            headers["X-Jain-User-Email"] = quote(user.email, safe="@")
            headers["X-Jain-User-Name"] = quote(user.name, safe="")
```

- [ ] **Step 4: Do the same in the proxy**

Edit `backend/app/routers/plugins.py`. In `call_plugin_api`, the external-proxy branch has its own header block. Replace:

```python
    if user is not None and settings.JAIN_SERVICE_KEY:
        headers["X-Jain-Service-Key"] = settings.JAIN_SERVICE_KEY
```

with:

```python
    plugin_service_key = getattr(plugin, "service_key", None) or settings.JAIN_SERVICE_KEY
    if user is not None and plugin_service_key:
        headers["X-Jain-Service-Key"] = plugin_service_key
```

Update the `_log.info` call's `service_key_configured` argument accordingly.

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_tool_executor.py tests/test_plugins_router.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/tool_executor.py backend/app/routers/plugins.py backend/tests/test_tool_executor.py
git commit -m "feat(executor): use per-plugin service keys from installed_plugins"
```

---

### Task 33: Deprecate `JAIN_SERVICE_KEY` with startup warning

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_config.py`:

```python
def test_deprecation_warning_when_jain_service_key_set(caplog):
    import importlib
    import logging

    caplog.set_level(logging.WARNING, logger="jain.config")

    from app import config as config_module
    importlib.reload(config_module)

    # Simulate reload with a value set
    config_module.settings.JAIN_SERVICE_KEY = "some-legacy-value"
    config_module.warn_if_service_key_set(config_module.settings)

    messages = [r.message for r in caplog.records if "jain.config" in r.name]
    assert any("JAIN_SERVICE_KEY" in m and "deprecated" in m.lower() for m in messages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_config.py::test_deprecation_warning_when_jain_service_key_set -v`
Expected: FAIL — `warn_if_service_key_set` doesn't exist.

- [ ] **Step 3: Replace the existing warning with a deprecation warning**

Edit `backend/app/config.py`. Replace the bottom-of-file JAIN_SERVICE_KEY warning block with:

```python
def warn_if_service_key_set(s: "Settings") -> None:
    """Phase 3: JAIN_SERVICE_KEY is deprecated. Per-plugin service keys are
    stored on the installed_plugins table. Keep the env var working for one
    release cycle so deployments can migrate.
    """
    if s.JAIN_SERVICE_KEY:
        msg = (
            "JAIN_SERVICE_KEY env var is deprecated; use per-plugin service "
            "keys via POST /api/plugins/install. Legacy value will be used "
            "as a fallback for any external plugin without its own key."
        )
        logging.getLogger("jain.config").warning(msg)
        warnings.warn(msg, DeprecationWarning, stacklevel=1)


warn_if_service_key_set(settings)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "chore(config): deprecate JAIN_SERVICE_KEY in favor of per-plugin keys"
```

---

### Task 34: Throwaway external plugin fixture + end-to-end install/call/uninstall

**Files:**
- Create: `backend/tests/fixtures/fake_external_plugin.py`
- Test: `backend/tests/test_external_plugin_e2e.py`

- [ ] **Step 1: Write the fake external plugin**

Create `backend/tests/fixtures/fake_external_plugin.py`:

```python
"""In-process fake for a third-party external plugin.

Used by the install/call/uninstall integration test. Not a real service —
tests mock httpx to route calls here.
"""

FAKE_MANIFEST = {
    "name": "fake_weather",
    "version": "0.1.0",
    "type": "external",
    "description": "Returns a fixed weather string for tests",
    "skills": [
        {
            "name": "weather",
            "description": "Get weather.",
            "tools": ["get_weather"],
        }
    ],
    "api": {"base_url": "https://fake-weather.test"},
}


async def fake_get_weather() -> dict:
    return {"temp_c": 22, "conditions": "sunny"}
```

- [ ] **Step 2: Write the failing end-to-end test**

Create `backend/tests/test_external_plugin_e2e.py`:

```python
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token
from app.config import settings
from app.database import async_session, engine
from app.dependencies import get_registry, reset_registry_for_tests
from app.main import create_app
from app.models.base import Base
from app.models.user import User

from .fixtures.fake_external_plugin import FAKE_MANIFEST


class _FakeResponse:
    def __init__(self, status_code, payload, content_type="application/json"):
        import json
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload) if isinstance(payload, (dict, list)) else payload
        self.content = self.text.encode("utf-8")
        self.headers = {"content-type": content_type}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=httpx.Response(self.status_code))


@pytest.fixture
async def admin_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as s:
        user = User(
            id=uuid4(), email="admin@example.com", name="A",
            email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = create_access_token(str(user.id))

    orig = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com"
    reset_registry_for_tests()
    app = create_app()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, token
    finally:
        settings.JAIN_ADMIN_EMAILS = orig
        reset_registry_for_tests()


async def test_install_then_call_then_uninstall(admin_env):
    client, token = admin_env

    # 1. Install
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(200, FAKE_MANIFEST),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "https://fake-weather.test/plugin.json", "service_key": "sk"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201

    # 2. Plugin appears in the registry and in GET /api/plugins
    resp = await client.get("/api/plugins")
    names = [p["name"] for p in resp.json()["plugins"]]
    assert "fake_weather" in names

    # 3. Proxy-call the external plugin (mocked httpx)
    with patch("app.routers.plugins.httpx.AsyncClient") as Mock:
        instance = Mock.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_FakeResponse(200, {"temp_c": 22}))
        instance.request = AsyncMock(return_value=_FakeResponse(200, {"temp_c": 22}))
        resp = await client.post(
            "/api/plugins/fake_weather/call",
            json={"method": "GET", "path": "/weather", "body": None},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["temp_c"] == 22

    # 4. Uninstall
    resp = await client.delete(
        "/api/plugins/fake_weather",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # 5. Plugin no longer visible
    resp = await client.get("/api/plugins")
    names = [p["name"] for p in resp.json()["plugins"]]
    assert "fake_weather" not in names
```

- [ ] **Step 3: Run test**

Run: `cd backend && pytest tests/test_external_plugin_e2e.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/fixtures/fake_external_plugin.py backend/tests/test_external_plugin_e2e.py
git commit -m "test(plugins): end-to-end install/call/uninstall integration"
```

---

### Task 35: Install validation failure unit tests (bundle, content-type, size)

**Files:**
- Test: `backend/tests/test_plugins_install.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_plugins_install.py`:

```python
_WITH_BUNDLE = dict(_VALID_MANIFEST)
_WITH_BUNDLE["name"] = "bundled"
_WITH_BUNDLE["components"] = {
    "bundle": "https://weather.example.com/bundle.js",
    "exports": ["W"],
}


async def test_install_rejects_non_js_content_type(admin_client):
    client, token = admin_client
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        instance = Mock.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=[
            _FakeResponse(200, _WITH_BUNDLE),
            _FakeResponse(200, "body", content_type="text/html"),
        ])
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
    assert "content-type" in resp.json()["detail"].lower()


async def test_install_rejects_oversized_bundle(admin_client):
    client, token = admin_client

    big = _FakeResponse(200, "x", content_type="application/javascript")
    big.content = b"x" * (3 * 1024 * 1024)

    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        instance = Mock.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=[
            _FakeResponse(200, _WITH_BUNDLE), big,
        ])
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


async def test_install_rejects_tool_name_collision_with_existing(admin_client):
    client, token = admin_client
    manifest = dict(_VALID_MANIFEST)
    manifest["name"] = "collider"
    manifest["skills"] = [
        {"name": "s", "description": "d", "tools": ["create_yard_sale"]},
    ]
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(200, manifest),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 409
    assert "create_yard_sale" in resp.json()["detail"]
```

- [ ] **Step 2: Run tests**

Run: `cd backend && pytest tests/test_plugins_install.py -v`
Expected: PASS (Task 30's validation code already covers these paths).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_plugins_install.py
git commit -m "test(plugins): install validation failure cases"
```

---

## Stage 5: Cleanup and repo hygiene

### Task 36: Remove `JAIN_SERVICE_KEY` from config (hard deprecation)

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/engine/tool_executor.py`
- Modify: `backend/app/routers/plugins.py`
- Modify: `backend/tests/test_tool_executor.py`
- Modify: `backend/.env.example` (if it exists — verify first)

- [ ] **Step 1: Verify no code references remain in production paths**

Run: `cd backend && grep -rn "JAIN_SERVICE_KEY" app tests`

Expected: matches in `config.py`, `tool_executor.py`, `plugins.py`, and test files. The test files currently set the value to verify fallback behavior.

- [ ] **Step 2: Remove the field from `Settings`**

Edit `backend/app/config.py`. Delete the `JAIN_SERVICE_KEY` field and the `warn_if_service_key_set` function and its call.

- [ ] **Step 3: Remove legacy fallback from executor**

Edit `backend/app/engine/tool_executor.py`. Change:

```python
        plugin_service_key = getattr(plugin, "service_key", None) or settings.JAIN_SERVICE_KEY
```

to:

```python
        plugin_service_key = getattr(plugin, "service_key", None)
```

Remove the `from app.config import settings` import if nothing else uses it.

- [ ] **Step 4: Same change in the proxy router**

Edit `backend/app/routers/plugins.py`:

```python
    plugin_service_key = getattr(plugin, "service_key", None)
```

Remove `settings.JAIN_SERVICE_KEY` references from the proxy log lines.

- [ ] **Step 5: Update legacy tests**

Edit `backend/tests/test_tool_executor.py`. Remove/update tests that reference `settings.JAIN_SERVICE_KEY`:
- `test_execute_forwards_service_key_headers_when_user_present`: rewrite to set `plugin.service_key = "test-service-key-1234"` before calling and assert the same header. Remove the `settings.JAIN_SERVICE_KEY` manipulation.
- `test_execute_handles_unicode_user_name`: same rewrite.
- `test_execute_skips_user_headers_when_service_key_empty`: rewrite to ensure `plugin.service_key = None` (or unset) and assert no headers sent.

Example rewrite of the forwarding test:

```python
async def test_execute_forwards_service_key_headers_when_user_present(registry, httpx_mock):
    from uuid import uuid4
    from app.models.user import User

    plugin = registry.get_plugin("yardsailing")
    plugin.service_key = "test-service-key-1234"  # type: ignore[attr-defined]

    try:
        httpx_mock.add_response(
            method="GET",
            url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
            json={"sales": []},
        )

        user = User(
            id=uuid4(), email="jim@example.com", name="Jim Shelly",
            email_verified=True, google_sub="g-jim",
        )

        executor = ToolExecutor(registry=registry)
        await executor.execute(
            ToolCall(
                id="tc1", name="find_yard_sales",
                arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
            ),
            user=user,
        )

        sent = httpx_mock.get_requests()[0]
        assert sent.headers["x-jain-service-key"] == "test-service-key-1234"
        assert sent.headers["x-jain-user-email"] == "jim@example.com"
        assert sent.headers["x-jain-user-name"] == "Jim%20Shelly"
    finally:
        plugin.service_key = None  # type: ignore[attr-defined]
```

- [ ] **Step 6: Update `.env.example`**

Run: `cd backend && test -f .env.example && cat .env.example || echo "no .env.example"`

If it exists and contains `JAIN_SERVICE_KEY`, remove that line and add:

```
# Phase 3: comma-separated list of admin emails for plugin install/uninstall
JAIN_ADMIN_EMAILS=you@example.com
```

- [ ] **Step 7: Run full suite**

Run: `cd backend && pytest -x`
Expected: PASS. If anything references `settings.JAIN_SERVICE_KEY`, grep again and fix.

- [ ] **Step 8: Commit**

```bash
git add backend/app/config.py backend/app/engine/tool_executor.py backend/app/routers/plugins.py backend/tests/test_tool_executor.py
test -f backend/.env.example && git add backend/.env.example
git commit -m "refactor(config): remove deprecated JAIN_SERVICE_KEY"
```

---

### Task 37: Verify `jain-plugins/plugins/yardsailing/` removal and add `examples/hello-external/`

**Files:**
- Delete: `C:/Users/jimsh/repos/jain-plugins/plugins/yardsailing/` (verify — done in Task 26)
- Create: `C:/Users/jimsh/repos/jain-plugins/examples/hello-external/plugin.json`
- Create: `C:/Users/jimsh/repos/jain-plugins/examples/hello-external/main.py`
- Create: `C:/Users/jimsh/repos/jain-plugins/examples/hello-external/README.md`

- [ ] **Step 1: Confirm yardsailing is gone from jain-plugins**

```bash
cd C:/Users/jimsh/repos/jain-plugins && test ! -d plugins/yardsailing && echo "gone" || echo "still present"
```
Expected: `gone`. If still present, revisit Task 26.

- [ ] **Step 2: Create the hello-external reference plugin**

Create `C:/Users/jimsh/repos/jain-plugins/examples/hello-external/plugin.json`:

```json
{
  "name": "hello_external",
  "version": "0.1.0",
  "type": "external",
  "description": "Minimal external plugin that says hi. Reference implementation for plugin authors.",
  "author": "jain-plugins",
  "skills": [
    {
      "name": "hello",
      "description": "Say hi.",
      "tools": ["say_hi"]
    }
  ],
  "api": {
    "base_url": "http://localhost:9000"
  }
}
```

Create `C:/Users/jimsh/repos/jain-plugins/examples/hello-external/main.py`:

```python
"""Reference external plugin for JAIN.

Run with: uvicorn main:app --port 9000

Install in JAIN:
  curl -X POST http://localhost:8000/api/plugins/install \
    -H "Authorization: Bearer <admin-token>" \
    -H "Content-Type: application/json" \
    -d '{"manifest_url":"http://localhost:9000/plugin.json","service_key":"dev-key"}'
"""

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import json
import pathlib

app = FastAPI()


@app.get("/plugin.json")
def manifest():
    return json.loads(
        (pathlib.Path(__file__).parent / "plugin.json").read_text(encoding="utf-8"),
    )


class HelloArgs(BaseModel):
    who: str = "world"


@app.get("/say_hi")
def say_hi(who: str = "world", x_jain_service_key: str = Header("")):
    if x_jain_service_key != "dev-key":
        raise HTTPException(status_code=401, detail="bad service key")
    return {"greeting": f"hello, {who}"}
```

Create `C:/Users/jimsh/repos/jain-plugins/examples/hello-external/README.md`:

```markdown
# hello-external

The simplest possible JAIN external plugin. Copy this, change the manifest,
add your logic.

## Files

- `plugin.json` — tells JAIN your plugin's name, version, and tool shape.
- `main.py` — a FastAPI service exposing `/plugin.json` and one tool endpoint.

## Run locally

```bash
pip install fastapi uvicorn
uvicorn main:app --port 9000
```

## Install into JAIN

```bash
curl -X POST http://localhost:8000/api/plugins/install \
  -H "Authorization: Bearer <your-jain-admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"manifest_url":"http://localhost:9000/plugin.json","service_key":"dev-key"}'
```

Then in the JAIN mobile app, your `say_hi` tool is available to the LLM.

## Service key trust model

JAIN forwards `X-Jain-Service-Key` with every call. Check it. JAIN forwards
`X-Jain-User-Email` and `X-Jain-User-Name` (URL-encoded) to identify the
authenticated user — you trust these because you trust the service key.
```

- [ ] **Step 3: Commit in jain-plugins**

```bash
cd C:/Users/jimsh/repos/jain-plugins
git add examples/hello-external/
git commit -m "docs(examples): add hello-external reference plugin"
```

---

### Task 38: Write `jain-plugins/README.md` (plugin authoring guide)

**Files:**
- Modify/Create: `C:/Users/jimsh/repos/jain-plugins/README.md`

- [ ] **Step 1: Write the README**

Overwrite `C:/Users/jimsh/repos/jain-plugins/README.md`:

```markdown
# jain-plugins

SDK and examples for building external plugins for JAIN.

JAIN has two plugin tiers. **Internal** plugins live inside the JAIN repo
and run in-process. **External** plugins are standalone HTTP services that
JAIN proxies to. This repo is for building the latter.

## What is a plugin?

A plugin is a manifest JSON file plus an HTTP service that implements the
tools declared in the manifest. JAIN installs your plugin at runtime by
fetching the manifest URL and caching it.

## Manifest schema

```json
{
  "name": "weather",
  "version": "1.0.0",
  "type": "external",
  "description": "Weather lookup for any location",
  "author": "Jane Dev",
  "skills": [
    {
      "name": "weather",
      "description": "Get current weather.",
      "tools": ["get_weather"]
    }
  ],
  "api": {
    "base_url": "https://weather-plugin.example.com"
  },
  "components": {
    "bundle": "https://weather-plugin.example.com/bundle.js",
    "exports": ["WeatherCard"]
  }
}
```

- `type: "external"` is required. Internal plugins cannot be runtime-installed.
- Each skill lists tool names the LLM can invoke.
- Tool definitions live in `<base_url>/<tool_name>` by default, or a custom
  endpoint declared per tool.

## Tool declaration

For each tool your plugin exposes, JAIN needs:

```json
{
  "name": "get_weather",
  "description": "Get current weather for a location.",
  "input_schema": {
    "type": "object",
    "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}},
    "required": ["lat", "lng"]
  },
  "endpoint": "/weather",
  "method": "GET",
  "auth_required": false
}
```

Ship these alongside your manifest at `<base_url>/plugin.json`.

## Service key trust model

JAIN signs every proxied call to your plugin with three headers:

- `X-Jain-Service-Key` — a shared secret the admin set at install time.
  Validate this on every request.
- `X-Jain-User-Email` — URL-encoded email of the authenticated user.
- `X-Jain-User-Name` — URL-encoded display name.

If the service key is valid, trust the user headers as authoritative. JAIN
already verified a JWT before forwarding.

Anonymous calls (to tools where `auth_required: false`) arrive with NO
auth headers. Decide for yourself whether you serve anonymous users.

## UI component bundle

Optional. If your plugin renders a React Native component in the JAIN chat
UI, build a JS bundle and expose it at a URL JAIN can fetch during install.

Use esbuild (see `tools/build.ts` for the recommended config):

```js
import { build } from "esbuild";

await build({
  entryPoints: ["src/index.ts"],
  bundle: true,
  outfile: "dist/bundle.js",
  format: "iife",
  platform: "neutral",
  target: "es2020",
  jsx: "transform",
  external: ["react", "react-native"],
});
```

The bundle must:

- Be under 2 MiB.
- Have content-type `application/javascript` or `text/javascript`.
- Export the component names declared in `components.exports`.

## Install your plugin

```bash
curl -X POST https://jain.example.com/api/plugins/install \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"manifest_url":"https://weather.example.com/plugin.json","service_key":"<shared-secret>"}'
```

Admin only. JAIN validates the manifest, fetches the bundle if present, and
registers the plugin immediately. No JAIN restart.

## Uninstall

```bash
curl -X DELETE https://jain.example.com/api/plugins/weather \
  -H "Authorization: Bearer <admin-jwt>"
```

## See also

- `examples/hello-external/` — minimal reference plugin you can copy.
- `tools/build.ts` — shared esbuild config for UI bundles.
- JAIN repo `backend/app/plugins/yardsailing/` — a full internal plugin for comparison.
```

- [ ] **Step 2: Commit in jain-plugins**

```bash
cd C:/Users/jimsh/repos/jain-plugins
git add README.md
git commit -m "docs(readme): plugin authoring guide for phase 3"
```

---

### Task 39: Update mobile `useHydratePlugins` for runtime refresh

**Files:**
- Modify: `mobile/App.tsx`

- [ ] **Step 1: Add `AppState` + `useFocusEffect` refresh**

Edit `mobile/App.tsx`. Replace `useHydratePlugins` with:

```tsx
import { AppState, AppStateStatus } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { useCallback } from "react";

function useHydratePlugins() {
  const setPlugins = useAppStore((s) => s.setPlugins);

  const refresh = useCallback(async () => {
    try {
      const plugins = await listPlugins();
      setPlugins(plugins);
      console.log("[App] loaded plugins:", plugins.map((p) => p.name));
    } catch (e) {
      console.log("[App] failed to load plugins:", (e as Error).message);
    }
  }, [setPlugins]);

  // Initial load on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Refresh when app returns to foreground (runtime-installed plugins
  // should appear within a few seconds without app restart).
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state: AppStateStatus) => {
      if (state === "active") refresh();
    });
    return () => sub.remove();
  }, [refresh]);
}
```

**Note:** `useFocusEffect` requires a screen context, not App-level. The foreground `AppState` listener handles the "app unbackgrounded" case. For tab-focus refresh, the existing Phase 2B `useFocusEffect` in `ChatScreen` already calls `listPlugins()` — verify this and add it if missing:

Run: `cd mobile && grep -rn "useFocusEffect\|listPlugins" src/screens/ChatScreen.tsx`

If ChatScreen has a `useFocusEffect` but doesn't call `listPlugins`, add:

```tsx
import { listPlugins } from "../api/plugins";
import { useAppStore } from "../store/useAppStore";

// inside ChatScreen, alongside any existing useFocusEffect:
const setPlugins = useAppStore((s) => s.setPlugins);
useFocusEffect(
  useCallback(() => {
    listPlugins().then(setPlugins).catch(() => {});
  }, [setPlugins]),
);
```

- [ ] **Step 2: Manually verify no regressions**

Run: `cd mobile && npm run typecheck 2>&1 | head -50`
Expected: no new type errors.

- [ ] **Step 3: Commit**

```bash
git add mobile/App.tsx mobile/src/screens/ChatScreen.tsx
git commit -m "feat(mobile): refresh plugin list on foreground and tab focus"
```

---

### Task 40: Update JAIN repo root `README.md`

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/README.md` (if exists — else create)

- [ ] **Step 1: Check if README exists**

Run: `ls C:/Users/jimsh/repos/jain/README.md 2>&1`

- [ ] **Step 2: Add a "Plugin system" section**

If the README exists, append this section. If not, create a minimal one:

```markdown
## Plugin system (Phase 3)

JAIN has two plugin tiers:

- **Internal plugins** live under `backend/app/plugins/<name>/` as Python
  packages. They run in JAIN's process, share the SQLite database, and ship
  with a JAIN deployment. First-party code only.
- **External plugins** are standalone HTTP services installed at runtime
  via `POST /api/plugins/install`. JAIN proxies tool calls to them and
  forwards a per-plugin service key plus URL-encoded user identity headers.

**Writing an internal plugin:** see `backend/app/plugins/yardsailing/` as
the reference. Export a `register() -> PluginRegistration` function from
`__init__.py`. Define models in `models.py` (they auto-register on JAIN's
SQLAlchemy `Base`), routes in `routes.py`, tool handlers in `tools.py`.

**Writing an external plugin:** see the separate `jain-plugins` repo and
its `examples/hello-external/`.

**Installing an external plugin (admin only):**

```bash
curl -X POST http://localhost:8000/api/plugins/install \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"manifest_url":"https://my-plugin.example.com/plugin.json","service_key":"<shared-secret>"}'
```

Configure admins via `JAIN_ADMIN_EMAILS=you@example.com` in `backend/.env`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): phase 3 plugin system documentation"
```

---

### Task 41: Archive yardsailing repo (manual step, documented here)

**Files:**
- None (manual GitHub step)

- [ ] **Step 1: Add a final redirect commit to the yardsailing repo**

```bash
cd C:/Users/jimsh/repos/yardsailing
```

Overwrite `README.md`:

```markdown
# yardsailing

**This repo is archived.** Yardsailing is now a first-party internal plugin
inside JAIN:

https://github.com/<you>/jain — see `backend/app/plugins/yardsailing/`

All future development happens there.

Historical commits on this repo remain for reference. No new changes will
land here.
```

- [ ] **Step 2: Commit and push**

```bash
git add README.md
git commit -m "docs: archive — yardsailing moved into JAIN as internal plugin"
git push
```

- [ ] **Step 3: Manual GitHub step (noted for the human)**

- Go to https://github.com/<you>/yardsailing/settings
- Scroll to "Archive this repository"
- Click "Archive" and confirm
- The repo becomes read-only

This step cannot be automated from the plan and must be done by the human in a browser.

- [ ] **Step 4: No JAIN commit for this task.**

---

### Task 42: Final full-suite verification

**Files:**
- None.

- [ ] **Step 1: Backend suite**

Run: `cd backend && pytest -v`
Expected: ALL tests pass. Zero skipped. Zero warnings aside from the one deprecation we intentionally still log.

- [ ] **Step 2: Start backend and sanity-check endpoints**

Run: `cd backend && uvicorn app.main:app --port 8000 &`

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/plugins | head -200
```

Expected: health ok; `/api/plugins` lists at least `yardsailing` as `type: internal`. Kill the server.

- [ ] **Step 3: Mobile typecheck**

Run: `cd mobile && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Grep for stale references**

```bash
cd backend && grep -rn "JAIN_SERVICE_KEY\|api.yardsailing.sale" app 2>&1 || echo "clean"
```
Expected: `clean` or only comments/tests referencing the old state.

- [ ] **Step 5: No commit — verification only. If all four steps pass, Phase 3 is done.**

---

## Self-Review Notes

### Spec requirements verified covered

**Stage 1 (backend groundwork):**
- Task 1: `type: Literal["internal","external"] = "external"` on `PluginManifest`.
- Task 2: `handler: Callable | None = None` on `ToolDef` with `arbitrary_types_allowed=True` and `exclude=True` to keep it out of serialized output.
- Task 3: `InstalledPlugin` model rewritten to match spec columns exactly (name PK, manifest_url, manifest_json, service_key, bundle_path nullable, installed_at, installed_by FK users.id).
- Task 4: `PluginRegistry.register` / `unregister` with read API unchanged.
- Task 5: helper for test-time cache reset; `get_registry` still returns a singleton so install-time mutation is visible to chat requests.
- Task 6: full test suite passes as the non-breaking acceptance gate.

**Stage 2 (internal scaffolding):**
- Task 7: resolves the `app/plugins/` collision by moving core files to `app/plugins/core/` (addressed explicitly).
- Task 8: `PluginRegistration` dataclass with exactly the spec fields.
- Task 9: `InternalPluginLoader` + `ExternalPluginLoader` split; internal walks packages looking for `register()`.
- Task 10: both loaders wired into `_registry_singleton`.
- Task 11: tool executor forks on `tool.handler`.
- Task 12: `db: AsyncSession` threaded through ChatService → ToolExecutor → handler (not in the spec's task list but the spec explicitly calls for `await tool.handler(args, user=user, db=db)` in Stage 2, so db injection must exist).
- Task 13: internal dispatch branch in `/api/plugins/{name}/call`.
- Task 14: `_hello` throwaway plugin + end-to-end test.
- Task 15: `_hello` deletion.

**Stage 3 (yardsailing rewrite):**
- Task 16: plugin package + plugin.json with `type: "internal"`.
- Task 17: `Sale` model with FK to `users.id`, `yardsailing_sales` table name.
- Task 18: services (create/list/get).
- Task 19: routes (POST /sales, GET /sales, GET /sales/{id}).
- Task 20: tools.py with `create_yard_sale` (handler) and `show_sale_form` (ui_component).
- Task 21: `SaleForm.tsx` copied from jain-plugins into `components/`.
- Task 22: esbuild bundle at `bundle/yardsailing.js` — COMMITTED.
- Task 23: table creation via `create_all` (NOT Alembic — see gap below).
- Task 24: proxy dispatcher upgraded to honor `Depends(get_current_user)` via ASGI sub-request forwarding.
- Task 25: end-to-end chat → form → DB row integration test.
- Task 26: yardsailing deleted from jain-plugins repo.

**Stage 4 (external runtime install):**
- Task 27: `JAIN_ADMIN_EMAILS` + `get_current_admin_user`.
- Task 28: `ExternalPluginLoader.load_from_db`.
- Task 29: lifespan wiring for the DB-backed external loader.
- Task 30: `POST /api/plugins/install` with full validation chain.
- Task 31: `GET /api/plugins/installed` and `DELETE /api/plugins/{name}`.
- Task 32: per-plugin service key replaces `settings.JAIN_SERVICE_KEY` in both executor and proxy.
- Task 33: deprecation warning for `JAIN_SERVICE_KEY`.
- Task 34: throwaway external plugin end-to-end install/call/uninstall.
- Task 35: install validation unit tests (content-type, size, tool collision).

**Stage 5 (cleanup):**
- Task 36: hard removal of `JAIN_SERVICE_KEY` from code, `.env.example`, tests.
- Task 37: `examples/hello-external/` reference plugin in jain-plugins.
- Task 38: `jain-plugins/README.md` authoring guide.
- Task 39: mobile `useHydratePlugins` with `AppState` + tab-focus refresh.
- Task 40: JAIN root `README.md` update.
- Task 41: yardsailing repo archive (manual GitHub step documented).
- Task 42: final verification gate.

### Gaps and judgment calls (human attention warranted)

1. **No Alembic in the repo.** The spec calls for "empty Alembic migration for `installed_plugins`" (Stage 1) and "Alembic migration `add_yardsailing_sales_table`" (Stage 3). Reality: the backend uses `Base.metadata.create_all()` at lifespan startup. This plan substitutes model-import + `create_all` (Tasks 3, 17, 23). If Alembic gets introduced later, both tables are already shaped to snap into a fresh migration. **Action item for the human:** decide whether to introduce Alembic before or after Phase 3; the plan works either way but the tasks would need an Alembic wrapper added if the human wants it now.

2. **`InstalledPlugin` stub model already existed** with the wrong columns (`id/name/version/enabled`). The plan rewrites it (Task 3) rather than creating from scratch. No consumer touches the old columns, so this is safe.

3. **`app/plugins/` namespace collision.** Resolved by moving core files to `app/plugins/core/` in Task 7. This touches every file that imports `app.plugins.schema` / `app.plugins.registry` / `app.plugins.loader` — roughly 10 files. One big mechanical rename commit. Alternative considered and rejected: keep core files at `app/plugins/` and put plugin packages at `app/plugins_pkgs/` or similar — this breaks the spec's convention and adds a second magic directory.

4. **Internal dispatch for routes that use FastAPI dependencies.** Task 13's naive dispatcher only handles single-body-arg routes. Task 24 upgrades to a full ASGI sub-request forwarder, which reuses the outer request's Authorization header so `get_current_user` resolves the same user. This is the most subtle piece of the plan; if it breaks, the yardsailing routes can fall back to mounting directly on the outer app (already done in Task 19 via `include_router`) — the `/api/plugins/yardsailing/call` proxy dispatch and the direct `/api/plugins/yardsailing/sales` route produce identical effects because BOTH paths now reach the same mounted router.

5. **`JAIN_SERVICE_KEY` deprecation timing.** The spec says "deprecate, log WARNING, don't fail" in Stage 4 AND "remove entirely" in Stage 5. The plan does both in sequence: Task 33 deprecates with warning; Task 36 hard-removes. If the human wants a slower deprecation (ship Phase 3 with just the warning, remove in Phase 4), stop after Task 33.

6. **Mobile `useFocusEffect`.** The spec says "add `useFocusEffect` trigger on chat tab focus + `AppState` listener for foreground refresh." `useFocusEffect` only works inside a screen, not at `App.tsx` level. Task 39 splits this: `AppState` listener goes in `App.tsx`'s `useHydratePlugins`; the chat-tab-focus refresh goes into `ChatScreen.tsx`. The plan verifies whether `ChatScreen` already has a `useFocusEffect` and adds a `listPlugins()` call alongside it.

7. **Stage 3 Task 22 (UI bundle) introduces npm tooling inside `backend/`.** Slightly unusual — normally backend and frontend tooling are separated. Alternative: run the esbuild from the repo root or from mobile/. I chose to keep it inside the plugin package because it scopes the node_modules to one directory and makes the plugin self-contained. The `.gitignore` update in Step 5 of Task 22 prevents `node_modules` from being committed.

8. **`PLUGINS_DIR` setting.** Phase 3 keeps `settings.PLUGINS_DIR` pointing at the (now empty) `jain-plugins/plugins` directory. After Task 26 it's effectively unused because the external loader reads from the DB. I left it in place rather than removing it to avoid cascading config breaks. The human may want to delete it in a follow-up.

9. **Tool count: 42 total tasks, ~7-8 per stage except Stage 3 (11 tasks). Step count: approximately 180 individual checkbox steps.** Larger than the 25-35 target range; the jumbo Stage 3 rewrite (models + services + routes + tools + bundle + integration) plus the `core/` refactor in Task 7 drove the count up. Each task is still small enough to complete in one 10-15 minute sitting.

10. **No task for updating the chat service display_hint handling.** The spec explicitly lists this as "carries forward from Phase 2B — do NOT modify." I verified in `chat_service.py` that `__source: "jain_executor_ui"` handling already works for any tool with `ui_component` set, regardless of plugin type. The yardsailing `show_sale_form` tool will flow through unchanged.
