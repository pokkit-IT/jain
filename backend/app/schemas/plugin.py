from pydantic import BaseModel

from app.plugins.schema import PluginManifest


class PluginListResponse(BaseModel):
    plugins: list[PluginManifest]
