"""CSV + PDF export for a user's custody events over a date range."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .services import get_child, list_events

CSV_HEADERS = [
    "occurred_at", "type", "child", "notes", "location",
    "amount_usd", "category", "photo_count", "photo_urls",
]


async def export_csv(
    db: AsyncSession, user: User, *,
    child_id: str, from_dt: datetime, to_dt: datetime,
) -> bytes:
    child = await get_child(db, user, child_id)
    child_name = child.name if child else ""

    events = await list_events(
        db, user, child_id=child_id,
        from_dt=from_dt, to_dt=to_dt, limit=10_000, offset=0,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADERS)
    for e in events:
        amount = ""
        if e.amount_cents is not None:
            amount = f"{e.amount_cents / 100:.2f}"
        photo_urls = ";".join(f"/uploads/{p.original_path}" for p in (e.photos or []))
        w.writerow([
            e.occurred_at.isoformat(timespec="minutes"),
            e.type,
            child_name,
            e.notes or "",
            e.location or "",
            amount,
            e.category or "",
            len(e.photos or []),
            photo_urls,
        ])
    return buf.getvalue().encode("utf-8")


# ---------- PDF ----------


def _type_label(t: str) -> str:
    return {
        "pickup": "Pickup", "dropoff": "Dropoff", "activity": "Activity",
        "expense": "Expense", "text_screenshot": "Text screenshot",
        "medical": "Medical", "school": "School",
        "missed_visit": "Missed visit", "phone_call": "Phone call",
        "note": "Note",
    }.get(t, t)


async def export_pdf(
    db: AsyncSession, user: User, *,
    child_id: str, from_dt: datetime, to_dt: datetime,
) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image as RLImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    from app.config import settings

    uploads_root = Path(settings.UPLOADS_DIR)

    child = await get_child(db, user, child_id)
    child_name = child.name if child else ""

    events = await list_events(
        db, user, child_id=child_id,
        from_dt=from_dt, to_dt=to_dt, limit=10_000, offset=0,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()

    flow: list = []
    title = (
        f"Custody log — {child_name} — "
        f"{from_dt.date().isoformat()} to {to_dt.date().isoformat()}"
    )
    flow.append(Paragraph(title, styles["Title"]))
    flow.append(Spacer(1, 0.15 * inch))

    events_sorted = sorted(events, key=lambda e: e.occurred_at)
    current_day: str | None = None
    for e in events_sorted:
        day = e.occurred_at.date().isoformat()
        if day != current_day:
            current_day = day
            flow.append(Spacer(1, 0.1 * inch))
            flow.append(Paragraph(f"<b>{day}</b>", styles["Heading3"]))
        line = f"<b>{e.occurred_at.strftime('%H:%M')}</b> — {_type_label(e.type)}"
        if e.type == "expense" and e.amount_cents is not None:
            line += f" — ${e.amount_cents / 100:.2f}"
            if e.category:
                line += f" ({e.category})"
        if e.notes:
            line += f": {e.notes}"
        if e.location:
            line += f" · {e.location}"
        flow.append(Paragraph(line, styles["BodyText"]))
        for p in (e.photos or []):
            img_path = uploads_root / p.thumb_path
            if img_path.exists():
                try:
                    flow.append(RLImage(str(img_path), width=1.5 * inch, height=1.5 * inch))
                    flow.append(Spacer(1, 0.05 * inch))
                except Exception:
                    continue

    doc.build(flow)
    return buf.getvalue()
