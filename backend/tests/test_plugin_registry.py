from pathlib import Path

from app.plugins.registry import PluginRegistry

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
