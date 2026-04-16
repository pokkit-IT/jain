"""LLM tool definitions for the nutrition internal plugin.

Handlers return the standard response envelope:
    {"status": ..., "data": ..., "message": ..., "next_action": "none"}
"""

from app.plugins.core.schema import ToolDef  # noqa: F401  (re-used by later tasks)

TOOLS: list = []
