from app.plugins.custody import register


def test_register_returns_registration_with_name_and_version():
    reg = register()
    assert reg.name == "custody"
    assert reg.version == "1.0.0"
    assert reg.type == "internal"
    assert reg.tools == []


def test_plugin_json_exists_and_has_home_block():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "app" / "plugins" / "custody" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"] == "custody"
    assert data["type"] == "internal"
    assert data["home"]["component"] == "CustodyHome"
    assert data["home"]["label"] == "Custody"
