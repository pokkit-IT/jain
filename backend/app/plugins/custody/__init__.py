"""First-party internal custody plugin.

Logs visitation events (pickups, dropoffs, activities, expenses,
text-screenshot attachments, medical/school, missed visits, phone
calls, notes) against one or more children. Exposes LLM tools for
natural-language logging from chat, a rich home screen with status +
timeline, and a PDF/CSV export for any date range.
"""

from app.plugins.core.types import PluginRegistration


def register() -> PluginRegistration:
    from . import models  # noqa: F401  (registers tables on Base.metadata)
    from .routes import router
    from .tools import TOOLS

    return PluginRegistration(
        name="custody",
        version="1.0.0",
        type="internal",
        router=router,
        tools=TOOLS,
        ui_bundle_path="bundle/custody.js",
        ui_components=[
            "CustodyHome",
            "ExpenseForm",
            "TextCaptureForm",
            "EventForm",
            "ScheduleForm",
            "ScheduleListScreen",
            "ChildrenScreen",
            "ExportSheet",
        ],
    )
