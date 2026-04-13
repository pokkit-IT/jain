"""LLM tool definitions for the yardsailing internal plugin.

- `create_yard_sale`: persistent action, auth_required, handler calls
  services.create_sale and returns {"ok": True, "id": ...}.
- `show_sale_form`: UI-only, no handler, instructs the chat service to
  emit a `display_hint: "component:SaleForm"` via the tool executor's
  ui_component branch.
"""

from app.plugins.core.schema import ToolDef, ToolInputSchema

from .services import CreateSaleInput, create_sale, list_recent_sales


async def find_yard_sales_handler(args, user=None, db=None):
    """Search for yard sales. Currently returns all recent sales (no geo
    filtering — SQLite has no spatial support). A future phase can add
    lat/lng to the Sale model and filter by distance."""
    sales = await list_recent_sales(db, limit=50)
    return {
        "sales": [
            {
                "id": s.id,
                "title": s.title,
                "address": s.address,
                "description": s.description,
                "start_date": s.start_date,
                "end_date": s.end_date,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "lat": s.lat,
                "lng": s.lng,
            }
            for s in sales
        ],
    }


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
        name="find_yard_sales",
        description=(
            "Search for yard sales. Use this when the user asks about sales "
            "near them, wants to browse listings, or asks what yard sales are "
            "happening. Returns a list of recent yard sale listings."
        ),
        input_schema=ToolInputSchema(
            properties={
                "query": {
                    "type": "string",
                    "description": "Optional search term to filter by (not yet implemented — returns all)",
                },
            },
            required=[],
        ),
        handler=find_yard_sales_handler,
    ),
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
