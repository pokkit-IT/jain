"""LLM tool definitions for the custody plugin.

- log_custody_event: pickup/dropoff/activity/note/medical/school/phone_call/text_screenshot
- log_expense: amount + category; USD → cents conversion in the handler
- log_missed_visit: manual entry for denied/missed visits
- query_custody_events: read-side for "how much / when / what" questions
- show_custody_home / show_expense_form / show_text_capture: UI-only
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.plugins.core.schema import ToolDef, ToolInputSchema

from .services import (
    CreateEventInput,
    InvalidEventData,
    create_event,
    list_children,
    list_events,
    resolve_child,
)


async def _resolve_or_err(db, user, child_name: str | None) -> dict | Any:
    child = await resolve_child(db, user, name=child_name)
    if child is not None:
        return child
    rows = await list_children(db, user)
    return {
        "error": "child_not_found",
        "plugin": "custody",
        "known_children": [c.name for c in rows],
    }


def _parse_occurred_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


async def log_custody_event_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    etype = args.get("type")
    if etype is None:
        return {"error": "type_required", "plugin": "custody"}

    maybe = await _resolve_or_err(db, user, args.get("child_name"))
    if isinstance(maybe, dict):
        return maybe
    child = maybe

    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=child.id,
            type=etype,
            occurred_at=_parse_occurred_at(args.get("occurred_at")),
            notes=args.get("notes"),
            location=args.get("location"),
            overnight=bool(args.get("overnight", False)),
            call_connected=args.get("call_connected"),
        ))
    except InvalidEventData as e:
        return {"error": str(e), "plugin": "custody"}
    return {
        "ok": True,
        "id": evt.id,
        "summary": f"{etype} logged for {child.name} at {evt.occurred_at.isoformat(timespec='minutes')}",
    }


async def log_expense_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    amount_usd = args.get("amount_usd")
    if amount_usd is None:
        return {"error": "amount_usd_required", "plugin": "custody"}
    try:
        amount_cents = int(round(float(amount_usd) * 100))
    except (TypeError, ValueError):
        return {"error": "amount_usd_invalid", "plugin": "custody"}
    if amount_cents < 0:
        return {"error": "amount_usd_negative", "plugin": "custody"}

    maybe = await _resolve_or_err(db, user, args.get("child_name"))
    if isinstance(maybe, dict):
        return maybe
    child = maybe

    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=child.id,
            type="expense",
            occurred_at=_parse_occurred_at(args.get("occurred_at")),
            notes=args.get("description"),
            amount_cents=amount_cents,
            category=args.get("category"),
        ))
    except InvalidEventData as e:
        return {"error": str(e), "plugin": "custody"}
    return {
        "ok": True,
        "id": evt.id,
        "summary": f"Expense ${amount_cents/100:.2f} logged for {child.name}",
    }


async def log_missed_visit_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    raw = args.get("expected_pickup_at")
    if not raw:
        return {"error": "expected_pickup_at_required", "plugin": "custody"}
    try:
        occurred = datetime.fromisoformat(raw)
    except ValueError:
        return {"error": "expected_pickup_at_invalid", "plugin": "custody"}

    maybe = await _resolve_or_err(db, user, args.get("child_name"))
    if isinstance(maybe, dict):
        return maybe
    child = maybe

    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=child.id,
            type="missed_visit",
            occurred_at=occurred,
            notes=args.get("notes"),
            missed_source="manual",
        ))
    except InvalidEventData as e:
        return {"error": str(e), "plugin": "custody"}
    return {
        "ok": True,
        "id": evt.id,
        "summary": f"Missed visit recorded for {child.name} on {occurred.date()}",
    }


async def query_custody_events_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    child_name = args.get("child_name")
    child = None
    if child_name:
        child = await resolve_child(db, user, name=child_name)
        if child is None:
            return await _resolve_or_err(db, user, child_name)

    from_dt = _parse_occurred_at(args.get("from_date")) if args.get("from_date") else None
    to_dt = _parse_occurred_at(args.get("to_date")) if args.get("to_date") else None
    limit = int(args.get("limit") or 20)

    rows = await list_events(
        db, user,
        child_id=child.id if child else None,
        type=args.get("type"),
        from_dt=from_dt, to_dt=to_dt,
        limit=limit,
    )
    events = [
        {
            "id": e.id,
            "type": e.type,
            "occurred_at": e.occurred_at.isoformat(timespec="minutes"),
            "notes": e.notes,
            "amount_usd": (e.amount_cents / 100) if e.amount_cents is not None else None,
            "category": e.category,
            "location": e.location,
        }
        for e in rows
    ]
    total_cents = sum(e.amount_cents or 0 for e in rows if e.type == "expense")
    by_type: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for e in rows:
        by_type[e.type] = by_type.get(e.type, 0) + 1
        if e.type == "expense" and e.amount_cents is not None:
            key = e.category or "other"
            by_category[key] = by_category.get(key, 0) + e.amount_cents
    return {
        "events": events,
        "summary": {
            "count": len(events),
            "total_expense_usd": round(total_cents / 100, 2),
            "by_type": by_type,
            "by_category_usd": {k: round(v / 100, 2) for k, v in by_category.items()},
        },
    }


TOOLS: list[ToolDef] = [
    ToolDef(
        name="log_custody_event",
        description=(
            "Log a single visitation event (pickup, dropoff, activity, note, "
            "medical, school, phone_call, text_screenshot). Use this for anything "
            "EXCEPT expenses (use log_expense) and missed visits (use log_missed_visit). "
            "occurred_at defaults to now if omitted."
        ),
        input_schema=ToolInputSchema(
            properties={
                "type": {
                    "type": "string",
                    "enum": [
                        "pickup", "dropoff", "activity", "note", "medical",
                        "school", "phone_call", "text_screenshot",
                    ],
                    "description": "Event type.",
                },
                "child_name": {
                    "type": "string",
                    "description": "Child's first name; omit if they have only one child.",
                },
                "occurred_at": {
                    "type": "string",
                    "description": "ISO-8601 datetime. Omit for 'now'.",
                },
                "notes": {"type": "string"},
                "location": {"type": "string"},
                "overnight": {"type": "boolean", "description": "Set on pickup when starting an overnight stay."},
                "call_connected": {"type": "boolean", "description": "For phone_call: did the call go through?"},
            },
            required=["type"],
        ),
        auth_required=True,
        handler=log_custody_event_handler,
    ),
    ToolDef(
        name="log_expense",
        description=(
            "Log a money expense during time with a child. Converts USD to cents "
            "server-side. Use when the user says they spent money (e.g. 'bowling $42')."
        ),
        input_schema=ToolInputSchema(
            properties={
                "child_name": {"type": "string"},
                "amount_usd": {"type": "number", "description": "Dollars (e.g. 42.50)."},
                "description": {
                    "type": "string",
                    "description": "What the expense was for.",
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "activity", "clothing", "school", "medical", "other"],
                },
                "occurred_at": {"type": "string"},
            },
            required=["amount_usd", "description"],
        ),
        auth_required=True,
        handler=log_expense_handler,
    ),
    ToolDef(
        name="log_missed_visit",
        description=(
            "Record a missed or denied visit (e.g. 'she didn't bring him Saturday'). "
            "Sets missed_source='manual' so the nightly auto-detector won't duplicate it."
        ),
        input_schema=ToolInputSchema(
            properties={
                "child_name": {"type": "string"},
                "expected_pickup_at": {
                    "type": "string",
                    "description": "ISO-8601 datetime of when the pickup was supposed to happen.",
                },
                "notes": {"type": "string"},
            },
            required=["expected_pickup_at"],
        ),
        auth_required=True,
        handler=log_missed_visit_handler,
    ),
    ToolDef(
        name="query_custody_events",
        description=(
            "Read-side: answer questions like 'how much have I spent on Mason this month?' "
            "or 'when did I last see him?'. Returns matching events and a summary block."
        ),
        input_schema=ToolInputSchema(
            properties={
                "child_name": {"type": "string"},
                "type": {"type": "string", "description": "Filter by event type."},
                "from_date": {"type": "string", "description": "ISO datetime lower bound."},
                "to_date": {"type": "string", "description": "ISO datetime upper bound."},
                "limit": {"type": "integer", "description": "Default 20, max 200."},
            },
            required=[],
        ),
        auth_required=True,
        handler=query_custody_events_handler,
    ),
    ToolDef(
        name="show_custody_home",
        description=(
            "Open the custody home screen (status, timeline, quick actions). "
            "Use when the user says 'open custody', 'show my timeline', or similar."
        ),
        input_schema=ToolInputSchema(),
        ui_component="CustodyHome",
    ),
    ToolDef(
        name="show_expense_form",
        description=(
            "Open the expense form with camera + category picker. Use when the user "
            "says 'log an expense', 'add a receipt', or similar."
        ),
        input_schema=ToolInputSchema(),
        ui_component="ExpenseForm",
    ),
    ToolDef(
        name="show_text_capture",
        description=(
            "Open the text-screenshot capture flow. Use when the user wants to save a "
            "screenshot of a text from the other parent."
        ),
        input_schema=ToolInputSchema(),
        ui_component="TextCaptureForm",
    ),
]
