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
