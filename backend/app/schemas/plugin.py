from pydantic import BaseModel

from app.plugins.core.schema import PluginManifest


class PluginListResponse(BaseModel):
    plugins: list[PluginManifest]
