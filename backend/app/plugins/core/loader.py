import json
from dataclasses import dataclass, field
from pathlib import Path

from .schema import PluginManifest, ToolDef


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    plugin_dir: Path
    tools: list[ToolDef] = field(default_factory=list)
    skill_prompts: dict[str, str] = field(default_factory=dict)  # skill_name -> markdown body


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from a markdown file body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return text
    return "\n".join(lines[end + 1 :]).lstrip()


def load_plugin(plugin_dir: Path) -> LoadedPlugin:
    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No plugin.json at {plugin_dir}")

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = PluginManifest.model_validate(json.load(f))

    tools: list[ToolDef] = []
    skill_prompts: dict[str, str] = {}

    for skill in manifest.skills:
        skill_dir = plugin_dir / "skills" / skill.name

        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            body = skill_md.read_text(encoding="utf-8")
            skill_prompts[skill.name] = _strip_frontmatter(body)
        else:
            skill_prompts[skill.name] = skill.description

        tools_json = skill_dir / "tools.json"
        if tools_json.exists():
            with tools_json.open("r", encoding="utf-8") as f:
                for tool_data in json.load(f):
                    tools.append(ToolDef.model_validate(tool_data))

    return LoadedPlugin(
        manifest=manifest,
        plugin_dir=plugin_dir,
        tools=tools,
        skill_prompts=skill_prompts,
    )


def load_plugins_from_dir(plugins_root: Path) -> list[LoadedPlugin]:
    if not plugins_root.exists():
        return []
    out: list[LoadedPlugin] = []
    for child in sorted(plugins_root.iterdir()):
        if child.is_dir() and (child / "plugin.json").exists():
            out.append(load_plugin(child))
    return out
