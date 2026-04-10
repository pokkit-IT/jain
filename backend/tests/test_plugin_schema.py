import pytest
from pydantic import ValidationError

from app.plugins.schema import PluginManifest, SkillDef, ToolDef, ToolInputSchema


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
