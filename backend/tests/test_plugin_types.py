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
