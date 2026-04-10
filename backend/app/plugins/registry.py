from pathlib import Path

from .loader import LoadedPlugin, load_plugins_from_dir
from .schema import PluginManifest, ToolDef


class PluginRegistry:
    def __init__(self, plugins_dir: Path | str):
        self.plugins_dir = Path(plugins_dir)
        self._plugins: dict[str, LoadedPlugin] = {}

    def load_all(self) -> None:
        self._plugins.clear()
        for plugin in load_plugins_from_dir(self.plugins_dir):
            self._plugins[plugin.manifest.name] = plugin

    def list_plugins(self) -> list[PluginManifest]:
        return [p.manifest for p in self._plugins.values()]

    def get_plugin(self, name: str) -> LoadedPlugin | None:
        return self._plugins.get(name)

    def all_tools(self) -> list[ToolDef]:
        tools: list[ToolDef] = []
        for plugin in self._plugins.values():
            tools.extend(plugin.tools)
        return tools

    def find_tool(self, tool_name: str) -> tuple[LoadedPlugin | None, ToolDef | None]:
        for plugin in self._plugins.values():
            for tool in plugin.tools:
                if tool.name == tool_name:
                    return plugin, tool
        return None, None

    def skill_descriptions(self) -> dict[str, str]:
        """Returns {plugin_name.skill_name: description} for all loaded skills."""
        out: dict[str, str] = {}
        for plugin in self._plugins.values():
            for skill in plugin.manifest.skills:
                key = f"{plugin.manifest.name}.{skill.name}"
                out[key] = skill.description
        return out
