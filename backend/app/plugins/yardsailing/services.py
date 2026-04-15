import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User

from .geocoding import geocode
from .models import Sale, SaleDay, SaleTag, sale_group_memberships
from .photos import sale_folder
from .tags import normalize as _norm_tag


@dataclass
class DayHours:
    day_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM


@dataclass
class CreateSaleInput:
    title: str
    address: str
    description: str | None
    start_date: str
    end_date: str | None
    start_time: str
    end_time: str
    tags: list[str] = field(default_factory=list)
    # Per-day overrides. When the sale spans multiple days and hours
    # vary, one entry per day that differs from the default.
    days: list[DayHours] = field(default_factory=list)


def _dates_in_range(start_iso: str, end_iso: str | None) -> list[str]:
    """Inclusive list of ISO dates from start to end. Returns [start] if end is None."""
    try:
        start = date.fromisoformat(start_iso)
    except ValueError:
        return [start_iso]
    if not end_iso:
        return [start_iso]
    try:
        end = date.fromisoformat(end_iso)
    except ValueError:
        return [start_iso]
    if end < start:
        return [start_iso]
    out: list[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def expanded_days(sale: Sale) -> list[dict]:
    """Authoritative per-day schedule for a sale.

    Returns one entry per date in [start_date, end_date], with hours
    coming from a SaleDay row when present or the Sale's defaults
    otherwise. Always safe to render in the UI.
    """
    out: list[dict] = []
    for d in _dates_in_range(sale.start_date, sale.end_date):
        start_t, end_t = sale.hours_for_day(d)
        out.append({"day_date": d, "start_time": start_t, "end_time": end_t})
    return out


def _day_rows_from_input(
    days: list[DayHours], default_start: str, default_end: str,
    start_date: str, end_date: str | None,
) -> list[SaleDay]:
    """Materialize SaleDay rows from input, skipping entries that match
    the defaults (no point storing an override that equals the fallback)."""
    if not days:
        return []
    valid_dates = set(_dates_in_range(start_date, end_date))
    rows: list[SaleDay] = []
    for d in days:
        if d.day_date not in valid_dates:
            continue
        if d.start_time == default_start and d.end_time == default_end:
            continue
        rows.append(SaleDay(
            day_date=d.day_date,
            start_time=d.start_time,
            end_time=d.end_time,
        ))
    return rows


def _normalize_tag_list(tags: list[str]) -> list[str]:
    """Lowercase, trim, dedupe, drop empties. Preserves input order."""
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        n = _norm_tag(t)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


async def create_sale(db: AsyncSession, user: User, data: CreateSaleInput) -> Sale:
    """Persist a new sale owned by `user`. Geocodes the address so the map can pin it."""
    coords = await geocode(data.address)
    lat, lng = coords if coords else (None, None)
    sale = Sale(
        owner_id=user.id,
        title=data.title,
        address=data.address,
        description=data.description,
        start_date=data.start_date,
        end_date=data.end_date,
        start_time=data.start_time,
        end_time=data.end_time,
        lat=lat,
        lng=lng,
    )
    for tag in _normalize_tag_list(data.tags):
        sale.tag_rows.append(SaleTag(tag=tag))
    for row in _day_rows_from_input(
        data.days, data.start_time, data.end_time, data.start_date, data.end_date,
    ):
        sale.day_rows.append(row)
    db.add(sale)
    await db.commit()
    await db.refresh(sale)
    return sale


async def list_sales_for_owner(db: AsyncSession, user: User) -> list[Sale]:
    """All sales owned by `user`, most recent first."""
    result = await db.execute(
        select(Sale)
        .options(selectinload(Sale.photos), selectinload(Sale.groups))
        .where(Sale.owner_id == user.id)
        .order_by(Sale.created_at.desc()),
    )
    return list(result.scalars().all())


async def list_recent_sales(
    db: AsyncSession,
    limit: int = 50,
    tags: list[str] | None = None,
    query: str | None = None,
    only_happening_now: bool = False,
    group_id: str | None = None,
) -> list[Sale]:
    """Upcoming/in-progress sales, most recent first.

    Args:
        tags: if given, returns sales having ANY of these tags (OR).
        query: case-insensitive LIKE across title, description, and tags.
        only_happening_now: restricts to sales where *right now* falls
            inside both the date range and the hours.
    """
    today = date.today().isoformat()
    effective_end = func.coalesce(Sale.end_date, Sale.start_date)

    stmt = select(Sale).options(selectinload(Sale.photos), selectinload(Sale.groups)).where(effective_end >= today)

    # only_happening_now is applied in Python after the query so we can
    # honor per-day SaleDay overrides. The cheap date bounds stay in SQL.
    if only_happening_now:
        stmt = stmt.where(
            Sale.start_date <= today,
            effective_end >= today,
        )

    if tags:
        wanted = [_norm_tag(t) for t in tags if t and t.strip()]
        if wanted:
            stmt = stmt.where(
                Sale.id.in_(
                    select(SaleTag.sale_id).where(SaleTag.tag.in_(wanted))
                )
            )

    if query and query.strip():
        q = f"%{query.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Sale.title).like(q),
                func.lower(Sale.description).like(q),
                Sale.id.in_(
                    select(SaleTag.sale_id).where(SaleTag.tag.like(q))
                ),
            )
        )

    if group_id:
        stmt = stmt.where(
            Sale.id.in_(
                select(sale_group_memberships.c.sale_id)
                .where(sale_group_memberships.c.group_id == group_id)
            )
        )

    stmt = stmt.order_by(Sale.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    sales = list(result.scalars().unique().all())

    if only_happening_now:
        now_time = datetime.now().strftime("%H:%M")
        sales = [
            s for s in sales
            if _is_open_now(s, today, now_time)
        ]

    return sales


def _is_open_now(sale: Sale, today: str, now_time: str) -> bool:
    start_t, end_t = sale.hours_for_day(today)
    return start_t <= now_time <= end_t


async def get_sale_by_id(db: AsyncSession, sale_id: str) -> Sale | None:
    result = await db.execute(
        select(Sale).options(selectinload(Sale.photos), selectinload(Sale.groups)).where(Sale.id == sale_id)
    )
    return result.scalar_one_or_none()


async def update_sale(
    db: AsyncSession, sale: Sale, data: CreateSaleInput,
) -> Sale:
    """Apply edits and re-geocode if the address changed."""
    if data.address != sale.address:
        coords = await geocode(data.address)
        sale.lat, sale.lng = coords if coords else (None, None)
    sale.title = data.title
    sale.address = data.address
    sale.description = data.description
    sale.start_date = data.start_date
    sale.end_date = data.end_date
    sale.start_time = data.start_time
    sale.end_time = data.end_time

    # Replace tags: clear existing, add normalized new set.
    sale.tag_rows.clear()
    for tag in _normalize_tag_list(data.tags):
        sale.tag_rows.append(SaleTag(tag=tag))

    # Replace per-day overrides the same way.
    sale.day_rows.clear()
    for row in _day_rows_from_input(
        data.days, data.start_time, data.end_time, data.start_date, data.end_date,
    ):
        sale.day_rows.append(row)

    await db.commit()
    await db.refresh(sale)
    return sale


async def delete_sale(db: AsyncSession, sale: Sale) -> None:
    sale_id = sale.id
    await db.delete(sale)
    await db.commit()
    shutil.rmtree(sale_folder(sale_id), ignore_errors=True)
