from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .geocoding import geocode
from .models import Sale


@dataclass
class CreateSaleInput:
    title: str
    address: str
    description: str | None
    start_date: str
    end_date: str | None
    start_time: str
    end_time: str


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


async def list_recent_sales(db: AsyncSession, limit: int = 50) -> list[Sale]:
    """All upcoming/in-progress sales, most recent first.

    Excludes sales whose end_date (or start_date, if no end_date) is in the
    past, so the map doesn't fill with stale pins.
    """
    today = date.today().isoformat()
    effective_end = func.coalesce(Sale.end_date, Sale.start_date)
    result = await db.execute(
        select(Sale)
        .where(effective_end >= today)
        .order_by(Sale.created_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


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
    await db.commit()
    await db.refresh(sale)
    return sale


async def delete_sale(db: AsyncSession, sale: Sale) -> None:
    await db.delete(sale)
    await db.commit()
