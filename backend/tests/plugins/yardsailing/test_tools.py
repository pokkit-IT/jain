from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale
from app.plugins.yardsailing.tools import (
    TOOLS,
    create_yard_sale_handler,
)


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


def test_tools_list_has_all_tools():
    names = {t.name for t in TOOLS}
    assert names == {"find_yard_sales", "create_yard_sale", "show_sale_form"}


def test_show_sale_form_is_ui_component():
    t = next(t for t in TOOLS if t.name == "show_sale_form")
    assert t.ui_component == "SaleForm"
    assert t.handler is None


def test_create_yard_sale_requires_auth():
    t = next(t for t in TOOLS if t.name == "create_yard_sale")
    assert t.auth_required is True
    assert t.handler is not None


async def test_create_yard_sale_handler_creates_row(session_and_user):
    session, user = session_and_user
    result = await create_yard_sale_handler(
        {
            "title": "Weekend Sale", "address": "100 Oak",
            "start_date": "2026-04-18", "start_time": "09:00", "end_time": "15:00",
        },
        user=user,
        db=session,
    )
    assert result["ok"] is True
    assert "id" in result

    from sqlalchemy import select
    rows = (await session.execute(select(Sale))).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "Weekend Sale"


async def test_create_yard_sale_handler_rejects_missing_user(session_and_user):
    session, _ = session_and_user
    result = await create_yard_sale_handler(
        {"title": "x", "address": "y",
         "start_date": "2026-04-18", "start_time": "09:00", "end_time": "15:00"},
        user=None,
        db=session,
    )
    assert result["error"] == "auth_required"
