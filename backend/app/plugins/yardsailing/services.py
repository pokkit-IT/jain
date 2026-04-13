from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .geocoding import geocode
from .models import Sale, SaleTag
from .tags import normalize as _norm_tag


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
    db.add(sale)
    await db.commit()
    await db.refresh(sale)
    return sale


async def list_sales_for_owner(db: AsyncSession, user: User) -> list[Sale]:
    """All sales owned by `user`, most recent first."""
    result = await db.execute(
        select(Sale).where(Sale.owner_id == user.id).order_by(Sale.created_at.desc()),
    )
    return list(result.scalars().all())


async def list_recent_sales(
    db: AsyncSession,
    limit: int = 50,
    tags: list[str] | None = None,
    query: str | None = None,
    only_happening_now: bool = False,
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

    stmt = select(Sale).where(effective_end >= today)

    if only_happening_now:
        now_time = datetime.now().strftime("%H:%M")
        stmt = stmt.where(
            Sale.start_date <= today,
            effective_end >= today,
            Sale.start_time <= now_time,
            Sale.end_time >= now_time,
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

    stmt = stmt.order_by(Sale.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_sale_by_id(db: AsyncSession, sale_id: str) -> Sale | None:
    return await db.get(Sale, sale_id)


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

    await db.commit()
    await db.refresh(sale)
    return sale


async def delete_sale(db: AsyncSession, sale: Sale) -> None:
    await db.delete(sale)
    await db.commit()
