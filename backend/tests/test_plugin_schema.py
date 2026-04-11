import pytest
from pydantic import ValidationError

from app.plugins.core.schema import PluginManifest, SkillDef, ToolDef, ToolInputSchema


def test_tool_def_parses():
    tool = ToolDef(
        name="find_yard_sales",
        description="Find yard sales",
        input_schema=ToolInputSchema(
            type="object",
            properties={"lat": {"type": "number"}, "lng": {"type": "number"}},
            required=["lat", "lng"],
        ),
    )
    assert tool.name == "find_yard_sales"
    assert "lat" in tool.input_schema.properties


def test_manifest_parses_minimal():
    data = {
        "name": "small-talk",
        "version": "1.0.0",
        "description": "Casual chat",
        "skills": [{"name": "chat", "description": "General chat"}],
    }
    m = PluginManifest.model_validate(data)
    assert m.name == "small-talk"
    assert len(m.skills) == 1
    assert m.components is None
    assert m.api is None


def test_manifest_parses_full():
    data = {
        "name": "yardsailing",
        "version": "1.0.0",
        "description": "Yard sales",
        "skills": [
            {
                "name": "find-sales",
                "description": "Find sales",
                "tools": ["find_yard_sales"],
            },
            {
                "name": "create-sale",
                "description": "Create sale",
                "tools": ["create_yard_sale"],
                "components": ["SaleForm"],
            },
        ],
        "components": {"bundle": "dist/components.bundle.js", "exports": ["SaleForm"]},
        "api": {"base_url": "https://api.yardsailing.sale"},
    }
    m = PluginManifest.model_validate(data)
    assert m.components.bundle == "dist/components.bundle.js"
    assert "SaleForm" in m.components.exports
    assert m.api.base_url == "https://api.yardsailing.sale"


def test_manifest_requires_name():
    with pytest.raises(ValidationError):
        PluginManifest.model_validate({"version": "1.0.0", "description": "x", "skills": []})


def test_plugin_manifest_type_defaults_to_external():
    m = PluginManifest(
        name="w", version="1", description="d", skills=[],
    )
    assert m.type == "external"


def test_plugin_manifest_type_accepts_internal():
    m = PluginManifest(
        name="y", version="1", description="d", skills=[], type="internal",
    )
    assert m.type == "internal"


def test_plugin_manifest_type_rejects_garbage():
    with pytest.raises(ValidationError):
        PluginManifest(
            name="x", version="1", description="d", skills=[], type="totally-wrong",
        )


def test_tool_def_handler_defaults_to_none():
    t = ToolDef(name="x", description="d", input_schema=ToolInputSchema())
    assert t.handler is None


def test_tool_def_handler_accepts_async_callable():
    async def h(args, user=None, db=None):
        return {"ok": True}

    t = ToolDef(
        name="x", description="d", input_schema=ToolInputSchema(), handler=h,
    )
    assert t.handler is h
