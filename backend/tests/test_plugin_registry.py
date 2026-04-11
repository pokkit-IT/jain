from pathlib import Path

from app.plugins.loader import LoadedPlugin
from app.plugins.registry import PluginRegistry
from app.plugins.schema import PluginManifest

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_registry_loads_and_lists():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    names = [p.name for p in reg.list_plugins()]
    assert "yardsailing" in names
    assert "small-talk" in names


def test_registry_find_tool():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    owner, tool = reg.find_tool("find_yard_sales")
    assert owner.manifest.name == "yardsailing"
    assert tool.endpoint == "/api/sales"


def test_registry_find_tool_missing():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()
    assert reg.find_tool("nonexistent") == (None, None)


def test_registry_all_tools():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    tools = reg.all_tools()
    assert len(tools) == 1
    assert tools[0].name == "find_yard_sales"


def test_registry_skill_descriptions():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    descs = reg.skill_descriptions()
    assert "yardsailing.find-sales" in descs
    assert "small-talk.chat" in descs
    assert "yard sales" in descs["yardsailing.find-sales"].lower()


def test_registry_register_adds_plugin(tmp_path):
    r = PluginRegistry(plugins_dir=tmp_path)
    manifest = PluginManifest(
        name="dynamic", version="1", description="d", skills=[],
    )
    loaded = LoadedPlugin(manifest=manifest, plugin_dir=tmp_path)
    r.register(loaded)

    assert r.get_plugin("dynamic") is loaded
    assert "dynamic" in [p.name for p in r.list_plugins()]


def test_registry_unregister_removes_plugin(tmp_path):
    r = PluginRegistry(plugins_dir=tmp_path)
    manifest = PluginManifest(
        name="dynamic", version="1", description="d", skills=[],
    )
    r.register(LoadedPlugin(manifest=manifest, plugin_dir=tmp_path))
    r.unregister("dynamic")

    assert r.get_plugin("dynamic") is None
    assert "dynamic" not in [p.name for p in r.list_plugins()]


def test_registry_unregister_missing_name_is_noop(tmp_path):
    r = PluginRegistry(plugins_dir=tmp_path)
    r.unregister("never-existed")  # must not raise
