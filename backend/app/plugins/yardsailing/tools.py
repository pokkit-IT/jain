"""LLM tool definitions for the yardsailing internal plugin.

- `create_yard_sale`: persistent action, auth_required, handler calls
  services.create_sale and returns {"ok": True, "id": ...}.
- `show_sale_form`: UI-only, no handler, instructs the chat service to
  emit a `display_hint: "component:SaleForm"` via the tool executor's
  ui_component branch.
"""

from app.plugins.core.schema import ToolDef, ToolInputSchema

from .services import CreateSaleInput, create_sale


async def create_yard_sale_handler(args, user=None, db=None):
    """Handler invoked by the tool executor for internal tool calls.

    Signature matches what `ToolExecutor.execute` passes: `(args, user, db)`.
    """
    if user is None:
        return {"error": "auth_required", "plugin": "yardsailing"}

    data = CreateSaleInput(
        title=args["title"],
        address=args["address"],
        description=args.get("description"),
        start_date=args["start_date"],
        end_date=args.get("end_date"),
        start_time=args["start_time"],
        end_time=args["end_time"],
    )
    sale = await create_sale(db, user, data)
    return {"ok": True, "id": str(sale.id)}


TOOLS: list[ToolDef] = [
    ToolDef(
        name="create_yard_sale",
        description=(
            "Create a new yard sale listing for the current user. Use this "
            "AFTER you have gathered title, address, start_date, start_time, "
            "and end_time. description and end_date are optional."
        ),
        input_schema=ToolInputSchema(
            properties={
                "title": {"type": "string", "description": "Short label for the sale"},
                "address": {"type": "string", "description": "Street address"},
                "description": {"type": "string", "description": "Optional details"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD, optional"},
                "start_time": {"type": "string", "description": "HH:MM (24h)"},
                "end_time": {"type": "string", "description": "HH:MM (24h)"},
            },
            required=["title", "address", "start_date", "start_time", "end_time"],
        ),
        auth_required=True,
        handler=create_yard_sale_handler,
    ),
    ToolDef(
        name="show_sale_form",
        description=(
            "Display an interactive form for the user to fill out a new yard "
            "sale listing. Use this when the user asks to 'fill out a form' "
            "or wants to see the fields before providing details."
        ),
        input_schema=ToolInputSchema(),
        ui_component="SaleForm",
    ),
]
