"""First-party internal yardsailing plugin.

Ships as part of the JAIN deployment. Shares JAIN's DB session and trust
boundary. Models live in `models.py`, HTTP routes in `routes.py`, business
logic in `services.py`, LLM tool definitions in `tools.py`.
"""

from app.plugins.core.types import PluginRegistration


def register() -> PluginRegistration:
    # Lazy imports: routes and tools modules are populated across Tasks
    # 17-20. Importing them here (at call time) lets the package be
    # imported cleanly between tasks without a broken top-level import.
    from .routes import router
    from .tools import TOOLS

    return PluginRegistration(
        name="yardsailing",
        version="1.0.0",
        type="internal",
        router=router,
        tools=TOOLS,
        ui_bundle_path="bundle/yardsailing.js",
        ui_components=["SaleForm", "YardsailingHome"],
    )
