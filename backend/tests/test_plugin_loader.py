from pathlib import Path

from app.plugins.core.loader import LoadedPlugin, load_plugin, load_plugins_from_dir

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_load_single_plugin_full():
    plugin = load_plugin(FIXTURES / "yardsailing")
    assert isinstance(plugin, LoadedPlugin)
    assert plugin.manifest.name == "yardsailing"
    assert plugin.manifest.api.base_url == "https://api.yardsailing.sale"
    assert len(plugin.manifest.skills) == 1
    assert len(plugin.tools) == 1
    assert plugin.tools[0].name == "find_yard_sales"
    assert "find_yard_sales" in plugin.skill_prompts["find-sales"]


def test_load_single_plugin_minimal():
    plugin = load_plugin(FIXTURES / "small-talk")
    assert plugin.manifest.name == "small-talk"
    assert plugin.manifest.api is None
    assert plugin.tools == []
    assert "friendly" in plugin.skill_prompts["chat"].lower()


def test_load_plugins_from_dir():
    plugins = load_plugins_from_dir(FIXTURES)
    names = [p.manifest.name for p in plugins]
    assert "yardsailing" in names
    assert "small-talk" in names
    assert len(plugins) == 2
