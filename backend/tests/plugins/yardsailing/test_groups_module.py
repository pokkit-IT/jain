import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.groups import (
    CreateGroupInput,
    GroupDateMismatch,
    GroupError,
    GroupNameTaken,
    attach_sale_to_group,
    create_group,
    detach_sale_from_group,
    search_groups,
    set_sale_groups,
    validate_dates_within_group,
)
from app.plugins.yardsailing.models import Sale, SaleGroup


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


async def _make_sale(session, user, *, start, end=None):
    from sqlalchemy import select
    sale = Sale(
        id=str(uuid.uuid4()), owner_id=user.id,
        title="t", address="a", description=None,
        start_date=start, end_date=end,
        start_time="08:00", end_time="17:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    await session.commit()
    res = await session.execute(select(Sale).where(Sale.id == sale.id))
    return res.scalar_one()


@pytest.mark.asyncio
async def test_create_group_basic(session_and_user):
    s, u = session_and_user
    g = await create_group(s, u, CreateGroupInput(name="Maple Street Sale"))
    assert g.slug == "maple-street-sale"
    assert g.start_date is None


@pytest.mark.asyncio
async def test_create_group_case_insensitive_name_unique(session_and_user):
    s, u = session_and_user
    await create_group(s, u, CreateGroupInput(name="100 Mile"))
    with pytest.raises(GroupNameTaken):
        await create_group(s, u, CreateGroupInput(name="100 mile"))


@pytest.mark.asyncio
async def test_create_group_slug_collision_suffixes(session_and_user):
    s, u = session_and_user
    g1 = await create_group(s, u, CreateGroupInput(name="abc 1"))
    g2 = await create_group(s, u, CreateGroupInput(name="abc-1"))
    assert g1.slug == "abc-1"
    assert g2.slug == "abc-1-2"


@pytest.mark.asyncio
async def test_create_group_date_window_validation(session_and_user):
    s, u = session_and_user
    with pytest.raises(GroupError):
        await create_group(
            s, u, CreateGroupInput(name="X", start_date="2026-05-01"),
        )
    with pytest.raises(GroupError):
        await create_group(
            s, u, CreateGroupInput(
                name="Y", start_date="2026-05-05", end_date="2026-05-01",
            ),
        )


@pytest.mark.asyncio
async def test_search_groups_prefix(session_and_user):
    s, u = session_and_user
    await create_group(s, u, CreateGroupInput(name="100 Mile Yard Sale"))
    await create_group(s, u, CreateGroupInput(name="Maple Street Sale"))
    assert [g.name for g in await search_groups(s, "100")] == ["100 Mile Yard Sale"]
    assert [g.name for g in await search_groups(s, "maple")] == ["Maple Street Sale"]
    assert len(await search_groups(s, "")) == 2


@pytest.mark.asyncio
async def test_validate_dates_within_group():
    s = Sale(start_date="2026-05-02", end_date="2026-05-03")
    g_open = SaleGroup(name="O", slug="o")
    g_exact = SaleGroup(
        name="E", slug="e", start_date="2026-05-01", end_date="2026-05-03",
    )
    g_before = SaleGroup(
        name="B", slug="b", start_date="2026-05-04", end_date="2026-05-05",
    )
    assert validate_dates_within_group(s, g_open)
    assert validate_dates_within_group(s, g_exact)
    assert not validate_dates_within_group(s, g_before)

    s_single = Sale(start_date="2026-05-02", end_date=None)
    assert validate_dates_within_group(s_single, g_exact)


@pytest.mark.asyncio
async def test_attach_and_detach_idempotent(session_and_user):
    s, u = session_and_user
    sale = await _make_sale(s, u, start="2026-05-02", end="2026-05-03")
    g = await create_group(s, u, CreateGroupInput(name="G"))

    await attach_sale_to_group(s, sale, g)
    await attach_sale_to_group(s, sale, g)  # idempotent
    assert len(sale.groups) == 1

    await detach_sale_from_group(s, sale, g)
    await detach_sale_from_group(s, sale, g)  # idempotent
    assert sale.groups == []


@pytest.mark.asyncio
async def test_attach_rejects_on_date_mismatch(session_and_user):
    s, u = session_and_user
    sale = await _make_sale(s, u, start="2026-06-01", end="2026-06-02")
    g = await create_group(
        s, u,
        CreateGroupInput(name="May", start_date="2026-05-01", end_date="2026-05-03"),
    )
    with pytest.raises(GroupDateMismatch):
        await attach_sale_to_group(s, sale, g)


@pytest.mark.asyncio
async def test_set_sale_groups_replaces_and_validates(session_and_user):
    s, u = session_and_user
    sale = await _make_sale(s, u, start="2026-05-02", end="2026-05-03")
    g1 = await create_group(s, u, CreateGroupInput(name="A"))
    g2 = await create_group(s, u, CreateGroupInput(name="B"))
    g_bad = await create_group(
        s, u,
        CreateGroupInput(name="C", start_date="2027-01-01", end_date="2027-01-02"),
    )

    out = await set_sale_groups(s, sale, [g1.id, g2.id])
    assert {g.id for g in out} == {g1.id, g2.id}

    # Replacing with just g1 drops g2
    out = await set_sale_groups(s, sale, [g1.id])
    assert [g.id for g in out] == [g1.id]

    # Empty list clears
    out = await set_sale_groups(s, sale, [])
    assert out == []

    # Mismatched group raises without partial mutation
    with pytest.raises(GroupDateMismatch):
        await set_sale_groups(s, sale, [g1.id, g_bad.id])
    assert sale.groups == []


@pytest.mark.asyncio
async def test_set_sale_groups_unknown_id_raises(session_and_user):
    s, u = session_and_user
    sale = await _make_sale(s, u, start="2026-05-02")
    with pytest.raises(GroupError):
        await set_sale_groups(s, sale, ["nope-not-a-real-id"])
