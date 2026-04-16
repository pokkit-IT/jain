"""First-party internal nutrition plugin.

Conversational meal logging and macro tracking. Phase 1 = text-only
(no UI bundle). Models live in `models.py`, business logic in
`services.py`, USDA lookup in `usda.py`, LLM tool definitions in
`tools.py`, admin/debug HTTP routes in `routes.py`.
"""

from app.plugins.core.types import PluginRegistration


def register() -> PluginRegistration:
    # Lazy imports so the package can be imported cleanly between tasks.
    from .routes import router
    from .tools import TOOLS

    return PluginRegistration(
        name="nutrition",
        version="1.0.0",
        type="internal",
        router=router,
        tools=TOOLS,
    )
