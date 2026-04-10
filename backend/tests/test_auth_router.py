from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.google_verify import InvalidGoogleTokenError, VerifiedGoogleClaims
from app.auth.jwt import sign_access_token
from app.database import get_db
from app.main import create_app
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def auth_client(session_factory):
    app = create_app()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_google_auth_success(auth_client):
    fake_claims = VerifiedGoogleClaims(
        sub="google-test-1",
        email="test@example.com",
        email_verified=True,
        name="Test User",
        picture="https://t.jpg",
    )
    with patch("app.routers.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = fake_claims
        response = await auth_client.post(
            "/api/auth/google",
            json={"id_token": "fake-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["user"]["email"] == "test@example.com"
    assert body["user"]["name"] == "Test User"
    assert body["user"]["picture_url"] == "https://t.jpg"
    assert "id" in body["user"]


async def test_google_auth_missing_id_token_returns_422(auth_client):
    response = await auth_client.post("/api/auth/google", json={})
    assert response.status_code == 422


async def test_google_auth_rejects_unverified_email(auth_client):
    fake_claims = VerifiedGoogleClaims(
        sub="google-test-1",
        email="test@example.com",
        email_verified=False,
        name="Test User",
        picture=None,
    )
    with patch("app.routers.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = fake_claims
        response = await auth_client.post(
            "/api/auth/google",
            json={"id_token": "fake-token"},
        )

    assert response.status_code == 401
    assert "email not verified" in response.json()["detail"].lower()


async def test_google_auth_invalid_token_returns_401(auth_client):
    with patch("app.routers.auth.verify_id_token") as mock_verify:
        mock_verify.side_effect = InvalidGoogleTokenError("bad signature")
        response = await auth_client.post(
            "/api/auth/google",
            json={"id_token": "fake-token"},
        )

    assert response.status_code == 401
    assert "invalid google token" in response.json()["detail"].lower()


async def test_get_me_without_token_returns_401(auth_client):
    response = await auth_client.get("/api/auth/me")
    assert response.status_code == 401


async def test_get_me_with_invalid_token_returns_401(auth_client):
    response = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 401


async def test_get_me_with_valid_token_returns_user(auth_client, session_factory):
    async with session_factory() as session:
        user = User(
            email="me@example.com",
            email_verified=True,
            google_sub="google-me",
            name="Me",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = sign_access_token(user)

    response = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@example.com"
    assert body["name"] == "Me"


async def test_get_me_for_deleted_user_returns_401(auth_client, session_factory):
    async with session_factory() as session:
        user = User(
            email="ghost@example.com",
            email_verified=True,
            google_sub="google-ghost",
            name="Ghost",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = sign_access_token(user)

        await session.delete(user)
        await session.commit()

    response = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
