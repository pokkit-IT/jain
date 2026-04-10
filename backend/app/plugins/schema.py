from typing import Any

from pydantic import BaseModel, Field


class ToolInputSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolDef(BaseModel):
    name: str
    description: str
    input_schema: ToolInputSchema
    # Optional: endpoint path on the plugin's api.base_url. Defaults to /{tool.name}.
    endpoint: str = ""
    # HTTP method. Defaults to GET. Use POST/PUT/DELETE for write operations.
    method: str = "GET"


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
    auth_required: bool = False


class PluginManifest(BaseModel):
    name: str
    version: str
    description: str
    author: str = ""
    skills: list[SkillDef]
    components: PluginComponents | None = None
    api: PluginApi | None = None
    assets: list[str] = Field(default_factory=list)
