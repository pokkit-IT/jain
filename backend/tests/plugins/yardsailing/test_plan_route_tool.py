from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.services import CreateSaleInput, create_sale, list_recent_sales
from app.plugins.yardsailing.tools import plan_route_handler


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        yield s, user
    await engine.dispose()


@pytest.mark.asyncio
async def test_plan_route_handler_orders_two_sales(session_and_user):
    session, user = session_and_user
    await create_sale(session, user, CreateSaleInput(
        title="Near", address="100 Main St", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
    ))
    await create_sale(session, user, CreateSaleInput(
        title="Far", address="200 Main St", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
    ))
    all_sales = await list_recent_sales(session, limit=10)
    ids = [s.id for s in all_sales]

    result = await plan_route_handler(
        {
            "sale_ids": ids,
            "start_location": {"lat": 0.0, "lng": 0.0},
        },
        user=user,
        db=session,
    )
    assert "route" in result
    assert result["route"]["stops"]
    assert len(result["route"]["stops"]) == 2


@pytest.mark.asyncio
async def test_plan_route_handler_missing_start_location(session_and_user):
    session, user = session_and_user
    result = await plan_route_handler(
        {"sale_ids": ["any"]},
        user=user,
        db=session,
    )
    assert result.get("error") == "start_location_required"
