"""Pin-drop sighting service.

A sighting is a Sale row with source='sighting'. First drop creates the
row with confirmations=1 ("Unconfirmed"). A second drop within 50 m on
the same calendar day bumps the nearest sighting's confirmations
("Confirmed"). Unconfirmed sightings expire from public listings 2
hours after creation.
"""

from datetime import date, datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .models import Sale


DROP_CUTOFF_HOUR = 17
DEDUP_RADIUS_METERS = 50.0
UNCONFIRMED_TTL_MINUTES = 120
SIGHTING_PLACEHOLDER_TITLE = "Unconfirmed sale"


class DropWindowClosed(Exception):
    """Raised when a drop is attempted at or after 17:00 local time."""


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0  # Earth radius in meters
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lng2 - lng1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _compute_end_time(now: datetime) -> str:
    """end_time = min(now + 2h, 17:00), formatted HH:MM."""
    plus_two = now + timedelta(hours=2)
    cutoff = now.replace(hour=17, minute=0, second=0, microsecond=0)
    chosen = min(plus_two, cutoff)
    return f"{chosen.hour:02d}:{chosen.minute:02d}"


def _format_coord_address(lat: float, lng: float) -> str:
    return f"{lat:.5f}, {lng:.5f}"


async def drop_sighting(
    db: AsyncSession,
    user: User,
    lat: float,
    lng: float,
    now: datetime,
    now_hhmm: str,
) -> Sale:
    """Create or bump a sighting at (lat, lng). Returns the resulting Sale.

    Args:
        now: server-local datetime used for start_time, end_time, created_at.
        now_hhmm: client-supplied local wall clock ("HH:MM") for the 17:00 gate.
    """
    if now_hhmm >= f"{DROP_CUTOFF_HOUR:02d}:00":
        raise DropWindowClosed(
            f"Drops are closed after {DROP_CUTOFF_HOUR:02d}:00 local time",
        )

    today = now.date().isoformat()
    res = await db.execute(
        select(Sale).where(
            Sale.source == "sighting",
            Sale.start_date == today,
            Sale.lat.is_not(None),
            Sale.lng.is_not(None),
        )
    )
    existing = list(res.scalars().all())

    nearest: Sale | None = None
    nearest_d = DEDUP_RADIUS_METERS + 1
    for s in existing:
        assert s.lat is not None and s.lng is not None
        d = haversine_meters(lat, lng, s.lat, s.lng)
        if d <= DEDUP_RADIUS_METERS and d < nearest_d:
            nearest, nearest_d = s, d

    if nearest is not None:
        nearest.confirmations += 1
        await db.commit()
        await db.refresh(nearest)
        return nearest

    start_time = f"{now.hour:02d}:{now.minute:02d}"
    sale = Sale(
        owner_id=user.id,
        title=SIGHTING_PLACEHOLDER_TITLE,
        address=_format_coord_address(lat, lng),
        description=None,
        start_date=today,
        end_date=today,
        start_time=start_time,
        end_time=_compute_end_time(now),
        lat=lat,
        lng=lng,
        source="sighting",
        confirmations=1,
    )
    db.add(sale)
    await db.commit()
    await db.refresh(sale)
    return sale
