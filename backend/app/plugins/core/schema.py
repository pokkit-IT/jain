from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolInputSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: ToolInputSchema
    # Optional: endpoint path on the plugin's api.base_url. Defaults to /{tool.name}.
    endpoint: str = ""
    # HTTP method. Defaults to GET. Use POST/PUT/DELETE for write operations.
    method: str = "GET"
    # Phase 2B: when True, the tool executor refuses to call this tool
    # unless the user is authenticated. Anonymous callers get a synthetic
    # auth_required error instead of an upstream HTTP call.
    auth_required: bool = False
    # Phase 2B: when set, the tool is a "client-side UI tool". Instead of
    # making an HTTP call to the plugin, the executor returns a synthetic
    # result that instructs the frontend to render the named component with
    # the tool's arguments as its initial props. Used for things like
    # "show the sale creation form" where no backend work is needed.
    ui_component: str | None = None
    # Phase 3: when set, the tool executor calls this Python callable
    # directly instead of making an HTTP request. Used by internal plugins.
    # Signature: async def handler(args: dict, user: User | None, db: AsyncSession) -> Any
    handler: Callable[..., Awaitable[Any]] | None = Field(default=None, exclude=True)


class SkillDef(BaseModel):
    name: str
    description: str
    tools: list[str] = Field(default_factory=list)  # tool names this skill exposes
    components: list[str] = Field(default_factory=list)  # component export names


class PluginComponents(BaseModel):
    bundle: str  # path to bundle file relative to plugin root
    exports: list[str]


class PluginApi(BaseModel):
    base_url: str


class PluginHome(BaseModel):
    """Optional home-screen declaration. The mobile Skills tab renders
    plugins that declare a home as tappable entries; tapping mounts
    `component` from the plugin bundle via PluginHost.
    """

    component: str  # exported React component name
    label: str  # user-facing label shown in the Skills list
    icon: str | None = None  # optional icon hint (mapped client-side)
    description: str | None = None  # one-line pitch; falls back to manifest.description


class MapConfig(BaseModel):
    component: str  # exported React component name rendered as map overlay


class HelpExample(BaseModel):
    prompt: str  # tappable text sent to chat when the user picks it
    description: str = ""  # optional one-liner explaining what it does


class PluginManifest(BaseModel):
    name: str
    version: str
    description: str
    author: str = ""
    type: Literal["internal", "external"] = "external"
    skills: list[SkillDef]
    components: PluginComponents | None = None
    api: PluginApi | None = None
    assets: list[str] = Field(default_factory=list)
    examples: list[HelpExample] = Field(default_factory=list)
    home: PluginHome | None = None
    map: MapConfig | None = None
