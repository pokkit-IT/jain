from dataclasses import dataclass

from sqlalchemy import select
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
    """All sales, most recent first. No geo filtering yet — returns everything."""
    result = await db.execute(
        select(Sale).order_by(Sale.created_at.desc()).limit(limit),
    )
    return list(result.scalars().all())


async def get_sale_by_id(db: AsyncSession, sale_id: str) -> Sale | None:
    return await db.get(Sale, sale_id)
