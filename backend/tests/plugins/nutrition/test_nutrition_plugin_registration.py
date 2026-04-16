from app.plugins.nutrition import register


def test_register_returns_internal_plugin():
    reg = register()
    assert reg.name == "nutrition"
    assert reg.version == "1.0.0"
    assert reg.type == "internal"
    assert reg.router is not None
    assert reg.router.prefix == "/api/plugins/nutrition"
    assert isinstance(reg.tools, list)
