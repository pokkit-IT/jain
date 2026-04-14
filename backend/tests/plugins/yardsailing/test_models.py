from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_sale_model_persist_and_load(session):
    user = User(
        id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
    )
    session.add(user)
    await session.flush()

    sale = Sale(
        owner_id=user.id,
        title="Big Saturday",
        address="123 Main",
        description="stuff",
        start_date="2026-04-18",
        end_date="2026-04-18",
        start_time="08:00",
        end_time="14:00",
    )
    session.add(sale)
    await session.commit()

    got = await session.get(Sale, sale.id)
    assert got is not None
    assert got.title == "Big Saturday"
    assert got.owner_id == user.id
    assert isinstance(got.created_at, datetime)


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid4(), email="x@y.com", name="X", email_verified=True, google_sub="g2",
        )
        s.add(user)
        await s.flush()
        yield s, user
    await engine.dispose()


@pytest.mark.asyncio
async def test_sale_photo_created_and_linked(session_and_user):
    from app.plugins.yardsailing.models import Sale, SalePhoto
    from sqlalchemy import select
    import uuid

    session, user = session_and_user
    sale = Sale(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    await session.flush()

    photo = SalePhoto(
        id=str(uuid.uuid4()),
        sale_id=sale.id,
        position=0,
        original_path=f"sales/{sale.id}/a.jpg",
        thumb_path=f"sales/{sale.id}/a-thumb.jpg",
        content_type="image/jpeg",
    )
    session.add(photo)
    await session.commit()

    res = await session.execute(select(SalePhoto).where(SalePhoto.sale_id == sale.id))
    loaded = res.scalar_one()
    assert loaded.position == 0
    assert loaded.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_deleting_sale_cascades_photos(session_and_user):
    from app.plugins.yardsailing.models import Sale, SalePhoto
    from sqlalchemy import select
    import uuid

    session, user = session_and_user
    sale_id = str(uuid.uuid4())
    sale = Sale(
        id=sale_id, owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    session.add(SalePhoto(
        id=str(uuid.uuid4()), sale_id=sale_id, position=0,
        original_path="p", thumb_path="t", content_type="image/jpeg",
    ))
    await session.commit()

    await session.delete(sale)  # ORM-level delete triggers cascade
    await session.commit()

    res = await session.execute(select(SalePhoto).where(SalePhoto.sale_id == sale_id))
    assert res.scalars().all() == []
