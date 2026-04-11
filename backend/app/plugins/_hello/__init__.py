"""Throwaway internal plugin proving the Stage 2 scaffolding.

Gets deleted at the end of Stage 2 (Task 15). Do not build on this.
"""

from app.plugins.core.schema import ToolDef, ToolInputSchema
from app.plugins.core.types import PluginRegistration


async def _hello_handler(args, user=None, db=None):
    who = args.get("who", "world")
    return {"greeting": f"hi, {who}"}


def register() -> PluginRegistration:
    return PluginRegistration(
        name="_hello",
        version="0.0.1",
        type="internal",
        tools=[
            ToolDef(
                name="hello_world",
                description="Say hi to someone.",
                input_schema=ToolInputSchema(
                    properties={"who": {"type": "string"}},
                    required=[],
                ),
                handler=_hello_handler,
            ),
        ],
    )
