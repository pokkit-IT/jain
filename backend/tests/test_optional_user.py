import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import sign_access_token
from app.auth.optional_user import get_current_user_optional
from app.config import settings
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def _make_request(authorization: str | None = None) -> Request:
    """Build a minimal Request object with the given Authorization header."""
    scope = {
        "type": "http",
        "headers": [(b"authorization", authorization.encode())] if authorization else [],
    }
    return Request(scope)


async def test_returns_user_for_valid_jwt(session):
    user = User(email="jim@example.com", name="Jim", email_verified=True, google_sub="g-1")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    token = sign_access_token(user)

    request = _make_request(f"Bearer {token}")
    result = await get_current_user_optional(request=request, db=session)
    assert result is not None
    assert result.id == user.id
    assert result.email == "jim@example.com"


async def test_returns_none_when_no_header(session):
    request = _make_request(None)
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_when_header_is_not_bearer(session):
    request = _make_request("Basic dXNlcjpwYXNz")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_for_bogus_jwt(session):
    request = _make_request("Bearer not-a-real-jwt")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_for_expired_jwt(session):
    user = User(email="e@x.com", name="E", email_verified=True, google_sub="g-e")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iat": int((now - timedelta(days=60)).timestamp()),
        "exp": int((now - timedelta(days=30)).timestamp()),
    }
    expired = pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    request = _make_request(f"Bearer {expired}")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None


async def test_returns_none_when_user_not_in_db(session):
    # Sign a JWT for a user that doesn't exist in the session
    ghost = User(id=uuid.uuid4(), email="ghost@x.com", name="G", email_verified=True)
    token = sign_access_token(ghost)

    request = _make_request(f"Bearer {token}")
    result = await get_current_user_optional(request=request, db=session)
    assert result is None
