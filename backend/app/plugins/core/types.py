from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from .schema import ToolDef

if TYPE_CHECKING:
    from fastapi import APIRouter


@dataclass
class PluginRegistration:
    """What an internal plugin's `register()` function returns.

    The loader uses this to wire the plugin's router into the FastAPI app,
    register tools with the global registry, and serve the plugin's UI
    bundle over `/api/plugins/{name}/bundle`.
    """

    name: str
    version: str
    type: Literal["internal", "external"]
    router: "APIRouter | None" = None
    tools: list[ToolDef] = field(default_factory=list)
    ui_bundle_path: str | None = None
    ui_components: list[str] = field(default_factory=list)
