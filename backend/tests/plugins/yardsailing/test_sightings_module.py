import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale
from app.plugins.yardsailing.sightings import (
    DropWindowClosed,
    _compute_end_time,
    drop_sighting,
    haversine_meters,
)


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid.uuid4(), email="u@g.com", name="U",
            email_verified=True, google_sub="gu",
        )
        s.add(user)
        await s.flush()
        yield s, user
    await engine.dispose()


def test_haversine_basic():
    # Two points ~50m apart at a mid-latitude
    d = haversine_meters(40.0, -74.0, 40.000449, -74.0)
    assert 49.5 <= d <= 50.5


def test_end_time_clamps_to_17():
    now = datetime(2026, 5, 2, 16, 30)
    assert _compute_end_time(now) == "17:00"


def test_end_time_uses_plus_two_when_earlier():
    now = datetime(2026, 5, 2, 10, 15)
    assert _compute_end_time(now) == "12:15"


@pytest.mark.asyncio
async def test_drop_creates_sighting(session_and_user):
    s, u = session_and_user
    now = datetime(2026, 5, 2, 10, 0)
    sale = await drop_sighting(s, u, 40.0, -74.0, now, "10:00")
    assert sale.source == "sighting"
    assert sale.confirmations == 1
    assert sale.start_date == "2026-05-02"
    assert sale.end_date == "2026-05-02"
    assert sale.start_time == "10:00"
    assert sale.end_time == "12:00"
    assert sale.address == "40.00000, -74.00000"


@pytest.mark.asyncio
async def test_drop_dedups_within_50m(session_and_user):
    s, u = session_and_user
    now = datetime(2026, 5, 2, 10, 0)
    first = await drop_sighting(s, u, 40.0, -74.0, now, "10:00")
    # ~30m north
    second = await drop_sighting(s, u, 40.00027, -74.0, now, "10:01")
    assert second.id == first.id
    assert second.confirmations == 2


@pytest.mark.asyncio
async def test_drop_no_merge_beyond_50m(session_and_user):
    s, u = session_and_user
    now = datetime(2026, 5, 2, 10, 0)
    first = await drop_sighting(s, u, 40.0, -74.0, now, "10:00")
    # ~100m north
    second = await drop_sighting(s, u, 40.0009, -74.0, now, "10:01")
    assert second.id != first.id
    assert second.confirmations == 1


@pytest.mark.asyncio
async def test_drop_no_merge_across_days(session_and_user):
    s, u = session_and_user
    yesterday = datetime(2026, 5, 1, 10, 0)
    today = datetime(2026, 5, 2, 10, 0)
    first = await drop_sighting(s, u, 40.0, -74.0, yesterday, "10:00")
    second = await drop_sighting(s, u, 40.0, -74.0, today, "10:00")
    assert second.id != first.id


@pytest.mark.asyncio
async def test_drop_rejects_after_cutoff(session_and_user):
    s, u = session_and_user
    now = datetime(2026, 5, 2, 17, 0)
    with pytest.raises(DropWindowClosed):
        await drop_sighting(s, u, 40.0, -74.0, now, "17:00")
    with pytest.raises(DropWindowClosed):
        await drop_sighting(s, u, 40.0, -74.0, now, "18:42")
