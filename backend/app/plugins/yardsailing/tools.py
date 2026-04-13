"""LLM tool definitions for the yardsailing internal plugin.

- `create_yard_sale`: persistent action, auth_required, handler calls
  services.create_sale and returns {"ok": True, "id": ...}.
- `show_sale_form`: UI-only, no handler, instructs the chat service to
  emit a `display_hint: "component:SaleForm"` via the tool executor's
  ui_component branch.
"""

import math

from app.plugins.core.schema import ToolDef, ToolInputSchema

from .services import CreateSaleInput, create_sale, list_recent_sales


_EARTH_RADIUS_MI = 3958.7613


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_MI * math.asin(math.sqrt(a))


async def find_yard_sales_handler(args, user=None, db=None):
    """Search for yard sales. Supports geo filter (lat/lng/radius_miles),
    tag filter, free-text query, and "happening now" filter."""
    tags = args.get("tags")
    if isinstance(tags, str):
        tags = [tags]
    query = args.get("query")
    only_happening_now = bool(args.get("only_happening_now"))

    sales = await list_recent_sales(
        db,
        limit=100,
        tags=tags or None,
        query=query,
        only_happening_now=only_happening_now,
    )

    lat = args.get("lat")
    lng = args.get("lng")
    radius = args.get("radius_miles")

    items = []
    for s in sales:
        item = {
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
            "tags": s.tags,
        }
        if lat is not None and lng is not None and s.lat is not None and s.lng is not None:
            d = _haversine_miles(float(lat), float(lng), s.lat, s.lng)
            item["distance_miles"] = round(d, 2)
        items.append(item)

    if lat is not None and lng is not None and radius is not None:
        items = [
            i for i in items
            if i.get("distance_miles") is not None and i["distance_miles"] <= float(radius)
        ]
        items.sort(key=lambda i: i["distance_miles"])

    return {"sales": items}


async def create_yard_sale_handler(args, user=None, db=None):
    """Handler invoked by the tool executor for internal tool calls.

    Signature matches what `ToolExecutor.execute` passes: `(args, user, db)`.
    """
    if user is None:
        return {"error": "auth_required", "plugin": "yardsailing"}

    tags_arg = args.get("tags") or []
    if isinstance(tags_arg, str):
        tags_arg = [tags_arg]
    data = CreateSaleInput(
        title=args["title"],
        address=args["address"],
        description=args.get("description"),
        start_date=args["start_date"],
        end_date=args.get("end_date"),
        start_time=args["start_time"],
        end_time=args["end_time"],
        tags=list(tags_arg),
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
                "lat": {
                    "type": "number",
                    "description": "User's latitude. Pass the value from [user location: ...] in the message.",
                },
                "lng": {
                    "type": "number",
                    "description": "User's longitude. Pass the value from [user location: ...] in the message.",
                },
                "radius_miles": {
                    "type": "number",
                    "description": "Search radius in miles. Default 25 if the user doesn't specify.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Filter to sales that have ANY of these tags. "
                        "Known tags: Furniture, Toys, Tools, Baby Items, "
                        "Clothing, Books, Electronics, Kitchen, Sports, "
                        "Garden, Holiday, Art, Free. Match is case-"
                        "insensitive so pass them however the user said them."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text search across title, description, and tags. "
                        "Use this when the user describes what they're looking "
                        "for in their own words rather than a known tag."
                    ),
                },
                "only_happening_now": {
                    "type": "boolean",
                    "description": (
                        "Set true when the user asks for sales happening right "
                        "now / currently open."
                    ),
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
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Category tags for this sale (e.g. ['Toys', 'Baby Items']). "
                        "Pick from the curated list when possible: Furniture, Toys, "
                        "Tools, Baby Items, Clothing, Books, Electronics, Kitchen, "
                        "Sports, Garden, Holiday, Art, Free."
                    ),
                },
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
