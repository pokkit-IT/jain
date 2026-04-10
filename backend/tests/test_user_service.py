import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.google_verify import VerifiedGoogleClaims
from app.models.base import Base
from app.models.user import User
from app.services.user_service import upsert_by_google


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def _claims(
    sub="google-user-1",
    email="alice@example.com",
    email_verified=True,
    name="Alice",
    picture=None,
) -> VerifiedGoogleClaims:
    return VerifiedGoogleClaims(
        sub=sub,
        email=email,
        email_verified=email_verified,
        name=name,
        picture=picture,
    )


async def test_insert_new_user(session):
    claims = _claims(
        sub="google-new-1",
        email="alice@example.com",
        name="Alice",
        picture="https://alice.jpg",
    )
    user = await upsert_by_google(session, claims)

    assert user.email == "alice@example.com"
    assert user.google_sub == "google-new-1"
    assert user.email_verified is True
    assert user.name == "Alice"
    assert user.picture_url == "https://alice.jpg"

    result = await session.execute(select(User))
    assert len(result.scalars().all()) == 1


async def test_update_user_matched_by_google_sub(session):
    await upsert_by_google(
        session, _claims(sub="sub-x", email="a@x.com", name="Old", picture=None)
    )
    updated = await upsert_by_google(
        session,
        _claims(sub="sub-x", email="a@x.com", name="New", picture="https://new.jpg"),
    )

    assert updated.name == "New"
    assert updated.picture_url == "https://new.jpg"

    result = await session.execute(select(User))
    assert len(result.scalars().all()) == 1


async def test_link_google_sub_to_existing_email_user(session):
    existing = User(
        email="bob@example.com",
        email_verified=False,
        google_sub=None,
        name="Bob",
    )
    session.add(existing)
    await session.commit()

    user = await upsert_by_google(
        session,
        _claims(
            sub="google-bob",
            email="bob@example.com",
            email_verified=True,
            name="Bob Full",
            picture="https://b.jpg",
        ),
    )

    assert user.google_sub == "google-bob"
    assert user.email_verified is True
    assert user.name == "Bob Full"
    assert user.picture_url == "https://b.jpg"

    result = await session.execute(select(User))
    assert len(result.scalars().all()) == 1


async def test_upsert_updates_last_login_at(session):
    first = await upsert_by_google(session, _claims(sub="sub-login"))
    first_login_at = first.last_login_at

    second = await upsert_by_google(session, _claims(sub="sub-login"))
    assert second.last_login_at >= first_login_at
