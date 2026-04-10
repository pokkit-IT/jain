# Phase 2A Implementation Plan: JAIN Identity + Google OAuth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real user identity layer to JAIN so users can sign in with Google from the Settings tab, get their profile stored in a JAIN `users` table, and receive a 30-day JAIN-issued JWT for subsequent requests.

**Architecture:** Mobile app opens Google OAuth via `expo-auth-session`, receives a Google ID token, sends it to JAIN's backend. Backend verifies the token against Google's public keys with `google-auth`, upserts a user row, signs its own HS256 JWT with `pyjwt`, and returns it. Mobile stores the JAIN JWT in `expo-secure-store` and sends it on subsequent requests via an axios interceptor. All Phase 1 endpoints remain anonymous-capable; sub-project A is purely additive.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.0 (async), pydantic v2, `google-auth>=2.35.0`, `pyjwt>=2.9.0`, pytest
- Mobile: Expo SDK 54, `expo-auth-session`, `expo-crypto`, `expo-web-browser`, `expo-secure-store`, Zustand, axios
- Reference spec: `docs/superpowers/specs/2026-04-10-phase-2a-jain-identity-google-oauth-design.md`

**Plan structure:**
- **Part 1 (Tasks 1–8):** Backend — config, model, schemas, JWT, Google verification, user service, dependency, router
- **Part 2 (Tasks 9–13):** Mobile — deps, token storage, auth API, store, axios, google flow, Settings UI, App hydration
- **Part 3 (Task 14):** Google Cloud Console setup + end-to-end acceptance walkthrough

---

## Part 1: Backend

### Task 1: Dependencies + config additions

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/backend/requirements.txt`
- Modify: `C:/Users/jimsh/repos/jain/backend/app/config.py`
- Test: run full existing suite to confirm nothing broke

- [ ] **Step 1: Add google-auth and pyjwt to requirements.txt**

Edit `backend/requirements.txt` — append these two lines at the end (keep all existing deps):

```
google-auth>=2.35.0
pyjwt>=2.9.0
```

- [ ] **Step 2: Install the new dependencies**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/pip install -r requirements.txt
```

Expected: both packages install cleanly. No errors about compilation.

- [ ] **Step 3: Add JWT + Google config fields**

Edit `backend/app/config.py`. Inside the `Settings` class (after `ANTHROPIC_API_KEY`), add:

```python
    # Google OAuth (sub-project A)
    GOOGLE_CLIENT_ID: str = ""

    # JAIN JWT signing (sub-project A)
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30
```

The default `JWT_SECRET` is intentionally obvious so developers notice and override it. Tests use this default directly.

- [ ] **Step 4: Run full existing test suite to confirm nothing broke**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest -q
```

Expected: all 37 existing tests pass. No new tests yet.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/requirements.txt backend/app/config.py
git commit -m "feat(backend): add google-auth + pyjwt deps and phase 2a config fields

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: User model

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/models/user.py`
- Test: `C:/Users/jimsh/repos/jain/backend/tests/test_user_model.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_user_model.py`:

```python
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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


async def test_create_user_with_defaults(session):
    u = User(
        email="jim@example.com",
        name="Jim Shelly",
        email_verified=True,
        google_sub="google-sub-123",
    )
    session.add(u)
    await session.commit()

    result = await session.execute(select(User))
    fetched = result.scalar_one()
    assert isinstance(fetched.id, UUID)
    assert fetched.email == "jim@example.com"
    assert fetched.email_verified is True
    assert fetched.google_sub == "google-sub-123"
    assert fetched.name == "Jim Shelly"
    assert fetched.picture_url is None
    assert fetched.last_login_at is not None


async def test_email_is_unique(session):
    u1 = User(email="dup@example.com", name="One", email_verified=True, google_sub="sub-1")
    u2 = User(email="dup@example.com", name="Two", email_verified=True, google_sub="sub-2")
    session.add(u1)
    await session.commit()
    session.add(u2)
    with pytest.raises(Exception):  # IntegrityError from sqlite
        await session.commit()


async def test_google_sub_is_unique(session):
    u1 = User(email="a@example.com", name="A", email_verified=True, google_sub="same-sub")
    u2 = User(email="b@example.com", name="B", email_verified=True, google_sub="same-sub")
    session.add(u1)
    await session.commit()
    session.add(u2)
    with pytest.raises(Exception):
        await session.commit()


async def test_google_sub_can_be_null(session):
    u = User(email="nosub@example.com", name="No Sub", email_verified=False, google_sub=None)
    session.add(u)
    await session.commit()

    result = await session.execute(select(User))
    fetched = result.scalar_one()
    assert fetched.google_sub is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_user_model.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.user'`.

- [ ] **Step 3: Implement the User model**

Create `backend/app/models/user.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    picture_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_user_model.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run full suite to confirm nothing else broke**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: previous 37 tests still pass, new 4 tests pass. Total 41.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/models/user.py backend/tests/test_user_model.py
git commit -m "feat(backend): add User SQLAlchemy model with unique email + google_sub

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Auth Pydantic schemas

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/schemas/auth.py`
- Test: `C:/Users/jimsh/repos/jain/backend/tests/test_auth_schemas.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_auth_schemas.py`:

```python
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.auth import GoogleAuthRequest, GoogleAuthResponse, UserOut


def test_google_auth_request_requires_id_token():
    req = GoogleAuthRequest(id_token="eyJ.fake.token")
    assert req.id_token == "eyJ.fake.token"


def test_google_auth_request_rejects_missing_id_token():
    with pytest.raises(ValidationError):
        GoogleAuthRequest.model_validate({})


def test_user_out_serializes():
    uid = uuid4()
    out = UserOut(
        id=uid,
        email="jim@example.com",
        name="Jim",
        picture_url="https://x.jpg",
    )
    dumped = out.model_dump()
    assert dumped["id"] == uid
    assert dumped["email"] == "jim@example.com"
    assert dumped["picture_url"] == "https://x.jpg"


def test_user_out_allows_null_picture():
    out = UserOut(id=uuid4(), email="a@b.c", name="A", picture_url=None)
    assert out.picture_url is None


def test_google_auth_response_shape():
    resp = GoogleAuthResponse(
        access_token="jwt-here",
        user=UserOut(id=uuid4(), email="a@b.c", name="A", picture_url=None),
    )
    assert resp.access_token == "jwt-here"
    assert resp.user.email == "a@b.c"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_auth_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.auth'`.

- [ ] **Step 3: Implement the schemas**

Create `backend/app/schemas/auth.py`:

```python
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoogleAuthRequest(BaseModel):
    id_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    picture_url: str | None = None


class GoogleAuthResponse(BaseModel):
    access_token: str
    user: UserOut
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_auth_schemas.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/schemas/auth.py backend/tests/test_auth_schemas.py
git commit -m "feat(backend): add Pydantic schemas for google auth and user output

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: JAIN JWT sign + verify module

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/auth/__init__.py`
- Create: `C:/Users/jimsh/repos/jain/backend/app/auth/jwt.py`
- Test: `C:/Users/jimsh/repos/jain/backend/tests/test_auth_jwt.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_auth_jwt.py`:

```python
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.auth.jwt import sign_access_token, verify_access_token
from app.config import settings
from app.models.user import User


def _make_user() -> User:
    user = User(
        id=uuid4(),
        email="jim@example.com",
        name="Jim Shelly",
        email_verified=True,
        google_sub="google-sub-1",
    )
    return user


def test_sign_and_verify_roundtrip():
    user = _make_user()
    token = sign_access_token(user)
    claims = verify_access_token(token)

    assert claims["sub"] == str(user.id)
    assert claims["email"] == "jim@example.com"
    assert claims["name"] == "Jim Shelly"
    assert "iat" in claims
    assert "exp" in claims


def test_token_expires_in_configured_days():
    user = _make_user()
    token = sign_access_token(user)
    claims = verify_access_token(token)

    iat = claims["iat"]
    exp = claims["exp"]
    delta_seconds = exp - iat
    expected_seconds = settings.JWT_EXPIRE_DAYS * 24 * 60 * 60
    # Allow 5 seconds of test jitter
    assert abs(delta_seconds - expected_seconds) < 5


def test_tampered_signature_rejected():
    user = _make_user()
    token = sign_access_token(user)
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(pyjwt.InvalidSignatureError):
        verify_access_token(tampered)


def test_expired_token_rejected():
    user = _make_user()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iat": int((now - timedelta(days=60)).timestamp()),
        "exp": int((now - timedelta(days=30)).timestamp()),
    }
    expired = pyjwt.encode(
        payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        verify_access_token(expired)


def test_bogus_token_rejected():
    with pytest.raises(pyjwt.DecodeError):
        verify_access_token("not-a-real-token")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_auth_jwt.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`.

- [ ] **Step 3: Create the empty `auth` package marker**

Create `backend/app/auth/__init__.py` as an empty file.

- [ ] **Step 4: Implement the JWT module**

Create `backend/app/auth/jwt.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt

from app.config import settings
from app.models.user import User


def sign_access_token(user: User) -> str:
    """Sign a JAIN access token for the given user.

    Returns a JWT valid for settings.JWT_EXPIRE_DAYS days, signed with
    HS256 using settings.JWT_SECRET.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.JWT_EXPIRE_DAYS)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify a JAIN access token and return its claims.

    Raises:
        jwt.InvalidSignatureError: signature does not match
        jwt.ExpiredSignatureError: token has expired
        jwt.DecodeError: token is malformed
        jwt.InvalidTokenError: other validation failures
    """
    return pyjwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_auth_jwt.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/auth/__init__.py backend/app/auth/jwt.py backend/tests/test_auth_jwt.py
git commit -m "feat(backend): add JAIN JWT sign/verify module (HS256, 30-day)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Google ID token verification module

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/auth/google_verify.py`
- Test: `C:/Users/jimsh/repos/jain/backend/tests/test_google_verify.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_google_verify.py`:

```python
from unittest.mock import patch

import pytest

from app.auth.google_verify import (
    InvalidGoogleTokenError,
    VerifiedGoogleClaims,
    verify_id_token,
)


def test_verify_valid_token_returns_dataclass():
    fake_claims = {
        "sub": "google-user-123",
        "email": "jim@example.com",
        "email_verified": True,
        "name": "Jim Shelly",
        "picture": "https://lh3.googleusercontent.com/jim",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        result = verify_id_token("fake-id-token")

    assert isinstance(result, VerifiedGoogleClaims)
    assert result.sub == "google-user-123"
    assert result.email == "jim@example.com"
    assert result.email_verified is True
    assert result.name == "Jim Shelly"
    assert result.picture == "https://lh3.googleusercontent.com/jim"


def test_verify_invalid_token_raises():
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.side_effect = ValueError("Wrong audience")
        with pytest.raises(InvalidGoogleTokenError):
            verify_id_token("fake-id-token")


def test_verify_missing_email_verified_defaults_false():
    fake_claims = {
        "sub": "google-user-123",
        "email": "jim@example.com",
        "name": "Jim Shelly",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        result = verify_id_token("fake-id-token")

    assert result.email_verified is False


def test_verify_missing_picture_is_none():
    fake_claims = {
        "sub": "google-user-123",
        "email": "jim@example.com",
        "email_verified": True,
        "name": "Jim",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        result = verify_id_token("fake-id-token")

    assert result.picture is None


def test_verify_passes_client_id_to_google():
    from app.config import settings

    fake_claims = {
        "sub": "x",
        "email": "x@y.z",
        "email_verified": True,
        "name": "x",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        verify_id_token("token-str")

    args, kwargs = mock_verify.call_args
    # Called as verify_oauth2_token(token, request, client_id)
    assert args[0] == "token-str"
    assert args[2] == settings.GOOGLE_CLIENT_ID
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_google_verify.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.google_verify'`.

- [ ] **Step 3: Implement the Google verification module**

Create `backend/app/auth/google_verify.py`:

```python
from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config import settings


class InvalidGoogleTokenError(Exception):
    """Raised when a Google ID token fails verification."""


@dataclass(frozen=True)
class VerifiedGoogleClaims:
    sub: str
    email: str
    email_verified: bool
    name: str
    picture: str | None


def verify_id_token(id_token_str: str) -> VerifiedGoogleClaims:
    """Verify a Google ID token against Google's public keys.

    Returns the extracted claims on success. Raises InvalidGoogleTokenError
    on any failure (bad signature, wrong audience, expired, malformed, etc.).
    """
    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise InvalidGoogleTokenError(str(e)) from e

    return VerifiedGoogleClaims(
        sub=claims["sub"],
        email=claims["email"],
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name", ""),
        picture=claims.get("picture"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_google_verify.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/auth/google_verify.py backend/tests/test_google_verify.py
git commit -m "feat(backend): add google ID token verification module

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: User upsert service

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/services/user_service.py`
- Test: `C:/Users/jimsh/repos/jain/backend/tests/test_user_service.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_user_service.py`:

```python
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
    assert len(result.scalars().all()) == 1  # no duplicate


async def test_link_google_sub_to_existing_email_user(session):
    # Pre-existing user without google_sub (e.g. created via some future flow)
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

    # Second call should bump last_login_at
    second = await upsert_by_google(session, _claims(sub="sub-login"))
    assert second.last_login_at >= first_login_at
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_user_service.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.user_service'`.

- [ ] **Step 3: Implement the user service**

Create `backend/app/services/user_service.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google_verify import VerifiedGoogleClaims
from app.models.user import User


async def upsert_by_google(
    db: AsyncSession, claims: VerifiedGoogleClaims
) -> User:
    """Find or create a User matching the given Google claims.

    Matching strategy:
    1. Try to find by google_sub (stable Google identifier)
    2. Fall back to matching by email
    3. Create a new user if neither matches

    Always updates profile fields (name, picture_url, email_verified) and
    last_login_at from the incoming claims. Commits before returning.
    """
    now = datetime.now(timezone.utc)

    # Try google_sub first
    result = await db.execute(
        select(User).where(User.google_sub == claims.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Fall back to email
        result = await db.execute(
            select(User).where(User.email == claims.email)
        )
        user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=claims.email,
            email_verified=claims.email_verified,
            google_sub=claims.sub,
            name=claims.name,
            picture_url=claims.picture,
            last_login_at=now,
        )
        db.add(user)
    else:
        user.google_sub = claims.sub
        user.email_verified = claims.email_verified
        user.name = claims.name
        user.picture_url = claims.picture
        user.last_login_at = now

    await db.commit()
    await db.refresh(user)
    return user
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_user_service.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/services/user_service.py backend/tests/test_user_service.py
git commit -m "feat(backend): add user upsert service (matches by google_sub, falls back to email)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: get_current_user FastAPI dependency

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/auth/dependencies.py`

This task has no standalone unit test — it's tested end-to-end via the router tests in Task 8. FastAPI dependencies are hard to test in isolation without mocking the entire request, and the router test file covers all the interesting paths.

- [ ] **Step 1: Implement the dependency**

Create `backend/app/auth/dependencies.py`:

```python
from uuid import UUID

import jwt as pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import verify_access_token
from app.database import get_db
from app.models.user import User

# auto_error=False so we can return 401 (not 403) on missing credentials
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Authorization header.

    Raises 401 if:
    - No Authorization header
    - JWT is malformed, tampered, or expired
    - sub claim is not a valid UUID
    - User row no longer exists in the database
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="not authenticated")

    try:
        claims = verify_access_token(credentials.credentials)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="invalid token")

    try:
        user_id = UUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")

    return user
```

- [ ] **Step 2: Verify nothing breaks by running the full suite**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest -q
```

Expected: all existing tests pass (nothing imports `dependencies.py` yet, so this is just a sanity check that the file parses cleanly).

- [ ] **Step 3: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/auth/dependencies.py
git commit -m "feat(backend): add get_current_user FastAPI dependency

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Auth router + wire into main.py

**Files:**
- Create: `C:/Users/jimsh/repos/jain/backend/app/routers/auth.py`
- Modify: `C:/Users/jimsh/repos/jain/backend/app/main.py`
- Test: `C:/Users/jimsh/repos/jain/backend/tests/test_auth_router.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_auth_router.py`:

```python
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

        # Delete the user after issuing the token
        await session.delete(user)
        await session.commit()

    response = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_auth_router.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.routers.auth'`.

- [ ] **Step 3: Implement the auth router**

Create `backend/app/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.google_verify import InvalidGoogleTokenError, verify_id_token
from app.auth.jwt import sign_access_token
from app.database import get_db
from app.models.user import User
from app.schemas.auth import GoogleAuthRequest, GoogleAuthResponse, UserOut
from app.services.user_service import upsert_by_google

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google", response_model=GoogleAuthResponse)
async def google_auth(
    req: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> GoogleAuthResponse:
    try:
        claims = verify_id_token(req.id_token)
    except InvalidGoogleTokenError:
        raise HTTPException(status_code=401, detail="invalid google token")

    if not claims.email_verified:
        raise HTTPException(status_code=401, detail="email not verified")

    user = await upsert_by_google(db, claims)
    token = sign_access_token(user)

    return GoogleAuthResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
```

- [ ] **Step 4: Wire the router into main.py**

Edit `backend/app/main.py`. Add `auth` to the import and the `include_router` list:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import auth, chat, health, plugins
from .routers import settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="JAIN API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(plugins.router)
    app.include_router(settings_router.router)
    app.include_router(auth.router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the auth router tests**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest tests/test_auth_router.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Run full suite to verify nothing else broke**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: all Phase 1 tests (37) still pass + new tests from Tasks 2-8 pass. Target: ~55-57 tests total, all green.

- [ ] **Step 7: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add backend/app/routers/auth.py backend/app/main.py backend/tests/test_auth_router.py
git commit -m "feat(backend): add auth router (POST /api/auth/google, GET /api/auth/me)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Milestone: Backend complete.** The backend can now verify Google ID tokens, create users, issue JAIN JWTs, and authenticate requests via the Authorization header. Next: mobile.

---

## Part 2: Mobile

### Task 9: Install mobile dependencies + app.json scheme

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/mobile/package.json` (via npx expo install)
- Modify: `C:/Users/jimsh/repos/jain/mobile/app.json`

- [ ] **Step 1: Install expo-auth-session + dependencies**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx expo install expo-auth-session expo-crypto expo-web-browser expo-secure-store
```

Expected: all four packages install cleanly. `npx expo install` picks the SDK-compatible versions.

- [ ] **Step 2: Update app.json with the `scheme` and slug for OAuth redirect**

Read `C:/Users/jimsh/repos/jain/mobile/app.json` first to see the current structure. Then edit the `expo` block to:

1. Change `"slug"` from `"mobile"` to `"jain"` (if it's still `"mobile"`)
2. Change `"name"` from `"mobile"` to `"JAIN"` (if it's still `"mobile"`)
3. Add `"scheme": "jain"` inside the `expo` block (if not already present)

The relevant fields, after editing, should look like this:

```json
{
  "expo": {
    "name": "JAIN",
    "slug": "jain",
    "scheme": "jain",
    "version": "1.0.0",
    ...
  }
}
```

Preserve all other existing fields (`version`, `orientation`, `icon`, `userInterfaceStyle`, `splash`, `ios`, `android`, `web`, `plugins`, etc.) exactly as they are.

- [ ] **Step 3: Verify Metro restarts cleanly**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx expo start --clear
```

Expected: Metro starts without errors. Print the QR code. You can close it with Ctrl+C after confirming it started — actual mobile testing comes in Task 14.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/package.json mobile/package-lock.json mobile/app.json
git commit -m "feat(mobile): install expo-auth-session + related; set app scheme to jain

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Mobile token storage + auth API client

**Files:**
- Create: `C:/Users/jimsh/repos/jain/mobile/src/auth/tokenStorage.ts`
- Create: `C:/Users/jimsh/repos/jain/mobile/src/api/auth.ts`
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/types.ts`

- [ ] **Step 1: Add types for the user and session**

Edit `mobile/src/types.ts`. After the existing `Sale` interface, append:

```typescript
export interface JainUser {
  id: string;
  email: string;
  name: string;
  picture_url: string | null;
}

export interface Session {
  user: JainUser;
  token: string;
}
```

- [ ] **Step 2: Create the token storage wrapper**

Create `mobile/src/auth/tokenStorage.ts`:

```typescript
import * as SecureStore from "expo-secure-store";

const KEY = "jain.access_token";

export async function getToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEY);
  } catch {
    return null;
  }
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(KEY, token);
}

export async function clearToken(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(KEY);
  } catch {
    // already gone, ignore
  }
}
```

- [ ] **Step 3: Create the auth API client**

Create `mobile/src/api/auth.ts`:

```typescript
import { apiClient } from "./client";
import { JainUser, Session } from "../types";

interface GoogleAuthResponse {
  access_token: string;
  user: JainUser;
}

export async function signInWithGoogle(idToken: string): Promise<Session> {
  const { data } = await apiClient.post<GoogleAuthResponse>(
    "/api/auth/google",
    { id_token: idToken },
  );
  return { user: data.user, token: data.access_token };
}

export async function fetchCurrentUser(): Promise<JainUser> {
  const { data } = await apiClient.get<JainUser>("/api/auth/me");
  return data;
}
```

- [ ] **Step 4: Smoke test by importing in a Node REPL or just checking TypeScript compiles**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit
```

Expected: no type errors. If there are any, fix them before committing.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/src/types.ts mobile/src/auth/tokenStorage.ts mobile/src/api/auth.ts
git commit -m "feat(mobile): add token storage wrapper and auth API client

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Store session field + axios JWT interceptor

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/store/useAppStore.ts`
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/api/client.ts`

- [ ] **Step 1: Add session state to the store**

Edit `mobile/src/store/useAppStore.ts`. At the top, add `Session` to the imports from `../types`:

```typescript
import { ChatTurn, LocationState, PluginSummary, Sale, Session } from "../types";
```

Then inside the `AppState` interface, after the `auth: Record<string, boolean>;` and `setPluginAuth` lines, add:

```typescript
  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: Session | null;
  setSession: (session: Session | null) => void;
```

Then inside the `create<AppState>(...)` call, after the `setPluginAuth` implementation, add:

```typescript
  session: null,
  setSession: (session) => set({ session }),
```

The finished file's relevant new block looks like:

```typescript
  // Per-plugin auth state. Layer 1: hardcoded false until login UI lands.
  auth: { yardsailing: false },
  setPluginAuth: (plugin, authenticated) =>
    set((s) => ({ auth: { ...s.auth, [plugin]: authenticated } })),

  // Phase 2A: real JAIN session (Google OAuth). Null when signed out.
  session: null,
  setSession: (session) => set({ session }),
```

Note: the Phase 1 `auth: { yardsailing: false }` field stays in place. Sub-project B will wire the `session` into it.

- [ ] **Step 2: Add axios interceptor that attaches the JWT**

Edit `mobile/src/api/client.ts`. Replace the entire file contents with:

```typescript
import axios from "axios";
import { Platform } from "react-native";

import { getToken } from "../auth/tokenStorage";

const DEV_HOST = Platform.OS === "android" ? "10.0.2.2" : "localhost";
const API_BASE =
  process.env.EXPO_PUBLIC_JAIN_API_URL ?? `http://${DEV_HOST}:8000`;

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
});

// Attach the JAIN JWT to every outgoing request when present.
apiClient.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});
```

- [ ] **Step 3: Smoke test by running tsc**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/src/store/useAppStore.ts mobile/src/api/client.ts
git commit -m "feat(mobile): add session state to store and axios JWT interceptor

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Google OAuth flow via expo-auth-session

**Files:**
- Create: `C:/Users/jimsh/repos/jain/mobile/src/auth/googleAuth.ts`
- Modify: `C:/Users/jimsh/repos/jain/mobile/.env.example`

- [ ] **Step 1: Add the Google client ID env var to the example file**

Edit `mobile/.env.example`:

```
# Override the API base URL if running backend on a non-default host
# EXPO_PUBLIC_JAIN_API_URL=http://192.168.1.50:8000

# Google OAuth client ID (Web client type, from Google Cloud Console)
# See Task 14 of the Phase 2A plan for setup instructions.
EXPO_PUBLIC_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

- [ ] **Step 2: Implement the Google sign-in flow**

Create `mobile/src/auth/googleAuth.ts`:

```typescript
import * as AuthSession from "expo-auth-session";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";

// Required by expo-web-browser when returning from the OAuth redirect.
WebBrowser.maybeCompleteAuthSession();

const CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID ?? "";

/**
 * Hook that returns a `signIn` function plus reactive state.
 * Call this at the top of a React component:
 *
 *   const { signIn, ready } = useGoogleSignIn();
 *   ...
 *   <Button onPress={signIn} disabled={!ready} />
 */
export function useGoogleSignIn(): {
  signIn: () => Promise<string | null>;
  ready: boolean;
} {
  const [request, response, promptAsync] = Google.useAuthRequest({
    clientId: CLIENT_ID,
    scopes: ["openid", "email", "profile"],
    // Use the Expo proxy so we don't need per-platform redirect config.
    redirectUri: AuthSession.makeRedirectUri({ useProxy: true } as any),
  });

  const signIn = async (): Promise<string | null> => {
    if (!request) return null;
    const result = await promptAsync({ useProxy: true } as any);
    if (result?.type !== "success") return null;
    // The ID token is in result.params.id_token for the Google provider.
    const idToken = (result.params as { id_token?: string }).id_token;
    return idToken ?? null;
  };

  return { signIn, ready: request !== null };
}
```

- [ ] **Step 3: Smoke test by running tsc**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit
```

Expected: no type errors. The `as any` casts on `useProxy` are because `expo-auth-session` types for `useProxy` vary across SDK versions; the runtime behavior is stable.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/src/auth/googleAuth.ts mobile/.env.example
git commit -m "feat(mobile): add useGoogleSignIn hook using expo-auth-session proxy

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Settings screen Account section + App.tsx hydration

**Files:**
- Modify: `C:/Users/jimsh/repos/jain/mobile/src/screens/SettingsScreen.tsx`
- Modify: `C:/Users/jimsh/repos/jain/mobile/App.tsx`

- [ ] **Step 1: Update SettingsScreen to show the Account section**

Read the current `mobile/src/screens/SettingsScreen.tsx` first so you know the existing structure. Then replace its entire contents with:

```tsx
import React, { useEffect, useState } from "react";
import {
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { apiClient } from "../api/client";
import { listPlugins } from "../api/plugins";
import { signInWithGoogle } from "../api/auth";
import { useGoogleSignIn } from "../auth/googleAuth";
import { clearToken, setToken } from "../auth/tokenStorage";
import { useAppStore } from "../store/useAppStore";

interface Settings {
  mode: string;
  radius_miles: number;
  llm_provider: string;
  llm_model: string;
}

export function SettingsScreen() {
  const plugins = useAppStore((s) => s.plugins);
  const setPlugins = useAppStore((s) => s.setPlugins);
  const session = useAppStore((s) => s.session);
  const setSession = useAppStore((s) => s.setSession);

  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);

  const { signIn: googleSignIn, ready: googleReady } = useGoogleSignIn();

  useEffect(() => {
    (async () => {
      try {
        const [s, p] = await Promise.all([
          apiClient.get<Settings>("/api/settings"),
          listPlugins(),
        ]);
        setSettings(s.data);
        setPlugins(p);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [setPlugins]);

  const handleSignIn = async () => {
    if (signingIn) return;
    setSigningIn(true);
    try {
      const idToken = await googleSignIn();
      if (!idToken) {
        // User cancelled or something went wrong with Google flow
        return;
      }
      const newSession = await signInWithGoogle(idToken);
      await setToken(newSession.token);
      setSession(newSession);
    } catch (e) {
      Alert.alert("Sign-in failed", (e as Error).message || "Try again later.");
    } finally {
      setSigningIn(false);
    }
  };

  const handleSignOut = async () => {
    await clearToken();
    setSession(null);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Settings</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        {session ? (
          <View>
            <View style={styles.profileRow}>
              {session.user.picture_url ? (
                <Image
                  source={{ uri: session.user.picture_url }}
                  style={styles.avatar}
                />
              ) : (
                <View style={[styles.avatar, styles.avatarFallback]}>
                  <Text style={styles.avatarInitial}>
                    {(session.user.name || "?").charAt(0).toUpperCase()}
                  </Text>
                </View>
              )}
              <View style={styles.profileText}>
                <Text style={styles.profileName}>{session.user.name}</Text>
                <Text style={styles.profileEmail}>{session.user.email}</Text>
              </View>
            </View>
            <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
              <Text style={styles.signOutText}>Sign out</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View>
            <Text style={styles.row}>Not signed in</Text>
            <TouchableOpacity
              style={[styles.signInButton, (!googleReady || signingIn) && styles.signInDisabled]}
              onPress={handleSignIn}
              disabled={!googleReady || signingIn}
            >
              <Text style={styles.signInText}>
                {signingIn ? "Signing in..." : "Sign in with Google"}
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>LLM</Text>
        {settings ? (
          <>
            <Text style={styles.row}>Provider: {settings.llm_provider}</Text>
            <Text style={styles.row}>Model: {settings.llm_model}</Text>
            <Text style={styles.row}>Mode: {settings.mode}</Text>
          </>
        ) : (
          <Text style={styles.row}>Loading...</Text>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Installed Plugins</Text>
        {plugins.map((p) => (
          <View key={p.name} style={styles.plugin}>
            <Text style={styles.pluginName}>
              {p.name} v{p.version}
            </Text>
            <Text style={styles.pluginDesc}>{p.description}</Text>
            <Text style={styles.pluginSkills}>
              Skills: {p.skills.map((s) => s.name).join(", ")}
            </Text>
          </View>
        ))}
        {plugins.length === 0 ? <Text style={styles.row}>No plugins installed</Text> : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 16 },
  header: { fontSize: 28, fontWeight: "700", marginBottom: 16 },
  error: { color: "#b91c1c", marginBottom: 12 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  row: { fontSize: 14, color: "#374151", paddingVertical: 2 },

  profileRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    marginRight: 12,
  },
  avatarFallback: {
    backgroundColor: "#2563eb",
    alignItems: "center",
    justifyContent: "center",
  },
  avatarInitial: { color: "#fff", fontSize: 20, fontWeight: "600" },
  profileText: { flex: 1 },
  profileName: { fontSize: 16, fontWeight: "600", color: "#1f2937" },
  profileEmail: { fontSize: 13, color: "#64748b", marginTop: 2 },
  signOutButton: {
    marginTop: 12,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    alignItems: "center",
  },
  signOutText: { color: "#b91c1c", fontWeight: "600" },

  signInButton: {
    marginTop: 8,
    padding: 14,
    borderRadius: 10,
    backgroundColor: "#2563eb",
    alignItems: "center",
  },
  signInDisabled: { backgroundColor: "#94a3b8" },
  signInText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  plugin: {
    backgroundColor: "#fff",
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    marginBottom: 8,
  },
  pluginName: { fontSize: 16, fontWeight: "600" },
  pluginDesc: { fontSize: 14, color: "#64748b", marginTop: 2 },
  pluginSkills: { fontSize: 12, color: "#94a3b8", marginTop: 4 },
});
```

- [ ] **Step 2: Update App.tsx to hydrate the session on launch**

Read the current `mobile/App.tsx` first. Then replace its entire contents with:

```tsx
import "react-native-gesture-handler";
import React, { useEffect } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import { fetchCurrentUser } from "./src/api/auth";
import { clearToken, getToken } from "./src/auth/tokenStorage";
import { useAppStore } from "./src/store/useAppStore";
import { ChatScreen } from "./src/screens/ChatScreen";
import { MapScreen } from "./src/screens/MapScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";

const Tab = createBottomTabNavigator();

function useHydrateSession() {
  const setSession = useAppStore((s) => s.setSession);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;

      try {
        const user = await fetchCurrentUser();
        setSession({ user, token });
      } catch (e) {
        // Treat any error as "token is invalid" — clear it and show signed-out UI.
        // Note: this is slightly pessimistic for network errors; Phase 3 may want
        // to distinguish 401 from network failures.
        await clearToken();
        setSession(null);
      }
    })();
  }, [setSession]);
}

export default function App() {
  useHydrateSession();

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: "#2563eb" },
            headerTintColor: "#fff",
            tabBarActiveTintColor: "#2563eb",
          }}
        >
          <Tab.Screen name="Jain" component={ChatScreen} />
          <Tab.Screen name="Map" component={MapScreen} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
      </NavigationContainer>
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}
```

- [ ] **Step 3: Verify types compile**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/jimsh/repos/jain
git add mobile/src/screens/SettingsScreen.tsx mobile/App.tsx
git commit -m "feat(mobile): add Account section to Settings + hydrate session on launch

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Milestone: Mobile code complete.** The mobile app can now sign in with Google, store the JWT, and hydrate the session on launch. The only thing blocking end-to-end testing is the Google Cloud Console setup.

---

## Part 3: Setup + Acceptance

### Task 14: Google Cloud Console setup + end-to-end acceptance walkthrough

**Files:** none — this is user-performed setup plus a manual QA run.

This task has two phases. Phase A: the user creates a Google OAuth client in Google Cloud Console and populates `.env` files. Phase B: end-to-end smoke test against the success criteria.

#### Phase A: Google Cloud Console setup

- [ ] **Step 1: Create or select a Google Cloud project**

1. Open https://console.cloud.google.com in a browser (sign in with your Google account)
2. Click the project selector at the top → **New Project**
3. Name it "JAIN" (or reuse an existing project)
4. Click **Create** and wait for it to be provisioned (~10 seconds)
5. Select the new project from the project selector

- [ ] **Step 2: Configure the OAuth consent screen**

1. Left sidebar → **APIs & Services** → **OAuth consent screen**
2. User type: **External** → **Create**
3. App information:
   - App name: `JAIN`
   - User support email: your Google account email
   - Developer contact email: your Google account email
   - (Leave logo, app domain, etc. blank — not needed for Testing mode)
4. Click **Save and Continue**
5. Scopes: click **Add or Remove Scopes**, search for and add:
   - `.../auth/userinfo.email`
   - `.../auth/userinfo.profile`
   - `openid`
   - Click **Update** then **Save and Continue**
6. Test users: click **Add Users**, enter your own Google account email, click **Add** then **Save and Continue**
7. Review summary → **Back to Dashboard**
8. Publishing status stays at **Testing**. Do NOT click "Publish App" — Testing mode is the goal for sub-project A.

- [ ] **Step 3: Create an OAuth client ID**

1. Left sidebar → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `JAIN Expo Proxy`
5. Authorized JavaScript origins: leave blank
6. Authorized redirect URIs: click **Add URI**, then enter:

   ```
   https://auth.expo.io/@<your-expo-username>/jain
   ```

   To find your Expo username, run this in a terminal:

   ```bash
   cd C:/Users/jimsh/repos/jain/mobile
   npx expo whoami
   ```

   If you're not logged in to Expo: `npx expo login` first. If you don't have an Expo account, create one at https://expo.dev/signup (free).

   Replace `<your-expo-username>` in the redirect URI with your actual username. Example: `https://auth.expo.io/@jshelly/jain`.
7. Click **Create**
8. A modal shows the **Client ID** (ends in `.apps.googleusercontent.com`). **Copy it.**

- [ ] **Step 4: Populate backend `.env`**

If `backend/.env` already exists, edit it. Otherwise copy from the example:

```bash
cd C:/Users/jimsh/repos/jain/backend
cp .env.example .env   # if .env doesn't exist yet
```

Edit `backend/.env` and add/update these lines:

```env
GOOGLE_CLIENT_ID=<paste the Client ID from step 3 here>
JWT_SECRET=<generate with the command below>
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=30
```

Generate the `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste its output as the value of `JWT_SECRET`. Should be ~43 characters.

- [ ] **Step 5: Populate mobile `.env`**

Edit `mobile/.env` (create it if it doesn't exist). Add:

```env
EXPO_PUBLIC_GOOGLE_CLIENT_ID=<paste the same Client ID from step 3 here>
```

Keep any existing line like `EXPO_PUBLIC_JAIN_API_URL=http://192.168.12.218:8000` if present.

#### Phase B: End-to-end acceptance walkthrough

- [ ] **Step 6: Start the backend**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
curl http://localhost:8000/api/health
```

Expected: `{"status":"ok"}`.

- [ ] **Step 7: Start Metro**

```bash
cd C:/Users/jimsh/repos/jain/mobile
npx expo start --clear
```

Open the app on web (press `w` in Metro) or on your phone (scan the QR with Expo Go).

- [ ] **Step 8: Acceptance criteria walkthrough**

Go through each criterion from the spec. Record PASS / FAIL for each.

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | Backend: `POST /api/auth/google` accepts a valid Google ID token, creates/updates a user, returns JWT + user | Completed by steps 10-12 below (web sign-in flow exercises this endpoint) |
| 2 | Backend: `GET /api/auth/me` returns the current user for a valid JWT, 401 otherwise | Same flow; also verify logged-in `curl` below |
| 3 | Backend: all tests pass (existing + new) | Run `pytest -q` — expect ~55+ tests all green |
| 4 | Backend: sign-in with `email_verified: false` is rejected | Covered by `test_google_auth_rejects_unverified_email` — verify it was in the Task 8 test run |
| 5 | Mobile: Settings shows "Sign in with Google" button when logged out | Open the app — Settings tab should show the button |
| 6 | Mobile: tapping the button completes OAuth and shows profile | See step 10 |
| 7 | Mobile: closing and reopening the app preserves the logged-in state | See step 11 |
| 8 | Mobile: tapping "Sign out" clears the token and reverts to logged-out UI | See step 12 |
| 9 | Mobile: Phase 1 Layer 1 auth behavior still works | See step 13 |

- [ ] **Step 9: Run backend tests one more time to confirm green**

```bash
cd C:/Users/jimsh/repos/jain/backend
.venv/Scripts/python -m pytest -q
```

Expected: ~55-57 tests, all green. If any fail, do not proceed until they are fixed.

- [ ] **Step 10: Sign in with Google (the big moment)**

In the running app:

1. Tap the **Settings** tab
2. Tap **Sign in with Google**
3. An in-app browser opens to `accounts.google.com`
4. Sign in with the Google account you added as a test user in Phase A step 2
5. Google asks to grant `email`, `profile`, `openid` access — click **Allow**
6. Browser redirects back to the app
7. Settings screen should now show your avatar, name, and email at the top, with a **Sign out** button

**If anything fails here, the two most common causes are:**
- **"Access denied"** → Your Google account is not in the Test Users list. Go back to Phase A step 2, item 6, and add it.
- **"Redirect URI mismatch"** → The redirect URI in the Google Cloud Console Credentials doesn't match `https://auth.expo.io/@<your-expo-username>/jain`. Double-check the username and slug.

- [ ] **Step 11: Kill and reopen the app — still logged in**

1. In Expo Go on your phone, force-close the app (or in the web browser, refresh the page)
2. Reopen it
3. Tap Settings — you should see your profile immediately without re-signing-in. This verifies the `/api/auth/me` hydration path.

- [ ] **Step 12: Sign out**

1. Tap **Sign out** in Settings
2. Settings should revert to the "Not signed in" / "Sign in with Google" button
3. Kill and reopen the app — should stay signed out

- [ ] **Step 13: Verify Phase 1 Layer 1 behavior is intact**

1. Tap the **Jain** tab
2. Type `find yard sales near me` — should still work (real data, Map tab renders pins, etc.)
3. Type `I want to create a yard sale` — Jain should still refuse politely ("You'll need to sign in to yardsailing first...") because sub-project A does NOT wire the JAIN JWT into plugin calls. That's sub-project B's job.

If Jain DOES try to call create_yard_sale without the refusal, that's a bug — `auth: { yardsailing: false }` should still be sent. Check the chat request payload in the uvicorn logs.

- [ ] **Step 14: Verify with curl against the deployed backend (optional)**

Sign in via the app first to get a token. Then inspect the network request in the browser dev tools (if testing on web) to copy the JWT. Or add a temporary `console.log` in `useHydrateSession` to print it.

```bash
# Replace <JWT> with the actual token
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/auth/me
```

Expected: `{"id": "...", "email": "...", "name": "...", "picture_url": "..."}`.

```bash
curl -H "Authorization: Bearer not-real" http://localhost:8000/api/auth/me
```

Expected: `{"detail": "invalid token"}` with status 401.

```bash
curl http://localhost:8000/api/auth/me
```

Expected: `{"detail": "not authenticated"}` with status 401.

- [ ] **Step 15: Write acceptance report**

Create `C:/Users/jimsh/repos/jain/docs/superpowers/acceptance/2026-04-10-phase-2a.md`:

```markdown
# Phase 2A Acceptance — 2026-04-10

**Tested by:** Jim Shelly
**Branch:** `feature/phase-2a-identity-google-oauth`
**Backend tests:** <N>/<N> passing
**Result:** <Accepted | Deferred | Failed>

## Success Criteria

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | POST /api/auth/google accepts valid Google ID token, upserts user, returns JWT | <PASS/FAIL> | |
| 2 | GET /api/auth/me returns user for valid JWT, 401 otherwise | <PASS/FAIL> | |
| 3 | Backend: all tests pass | <PASS/FAIL> | <N>/<N> |
| 4 | Sign-in with email_verified=false rejected | <PASS/FAIL> | Covered by test_google_auth_rejects_unverified_email |
| 5 | Mobile Settings shows "Sign in with Google" when logged out | <PASS/FAIL> | |
| 6 | Tapping button completes OAuth, shows profile | <PASS/FAIL> | |
| 7 | Close/reopen preserves logged-in state | <PASS/FAIL> | |
| 8 | Sign out clears token, reverts UI | <PASS/FAIL> | |
| 9 | Phase 1 Layer 1 still works (Jain refuses create-sale) | <PASS/FAIL> | |
| 10 | Google Cloud Console setup was doable from the plan | <PASS/FAIL> | |

## Notes
<free-form observations, issues, workarounds>
```

Fill in the actual statuses.

- [ ] **Step 16: Final commit**

```bash
cd C:/Users/jimsh/repos/jain
git add docs/superpowers/acceptance/2026-04-10-phase-2a.md
git commit -m "docs: phase 2a acceptance report

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Phase 2A complete.** Sub-project B (plugin auth pass-through + yardsailing JWT bridge) is the next brainstorming cycle.

---

## Self-Review Notes

**Spec coverage:**
- User table schema → Task 2 ✓
- `POST /api/auth/google` → Task 8 ✓
- `GET /api/auth/me` → Task 8 ✓
- 30-day HS256 JWT → Task 4 ✓
- Google ID token verification → Task 5 ✓
- User upsert by google_sub with email fallback → Task 6 ✓
- `email_verified: false` rejection → Task 8 ✓ (test included)
- Mobile `expo-auth-session` Google flow → Task 12 ✓
- Token storage in `expo-secure-store` → Task 10 ✓
- Axios interceptor auto-attaching JWT → Task 11 ✓
- Settings tab sign-in/sign-out UI → Task 13 ✓
- Session hydration on app launch with `/api/auth/me` → Task 13 ✓
- Google Cloud Console setup walkthrough → Task 14 ✓
- `scheme: "jain"` in app.json → Task 9 ✓
- Phase 1 `auth: { yardsailing }` field preserved in parallel → Task 11 Step 1 ✓
- Phase 1 tests still pass — verified at every task's final step

**Open Questions from the spec — resolved inline:**
- `app.json` changes: slug → `jain`, scheme → `jain` (Task 9)
- Alembic: deferred to Phase 3 hygiene as the spec allowed; sub-project A doesn't need it
- Axios interceptor injection: module-load with `getToken()` via secure-store directly (Task 11 Step 2)
- `last_login_at` semantics: updated on every `POST /api/auth/google` call (Task 6 implementation)

**Placeholder scan:** no TBD/TODO/vague. Every code step has complete code. Commands have expected outputs.

**Type consistency check:**
- `VerifiedGoogleClaims` fields (sub, email, email_verified, name, picture) referenced consistently across Tasks 5, 6, 8
- `JainUser` TypeScript type (id, email, name, picture_url) matches backend `UserOut` Pydantic schema (Task 3 and Task 10)
- `Session` type (user: JainUser, token: string) consistent across Tasks 10, 11, 13
- `sign_access_token(user)` / `verify_access_token(token)` signatures consistent between Task 4 definition and Task 7, 8 usage
- `upsert_by_google(db, claims)` signature consistent between Task 6 definition and Task 8 usage
- `get_current_user` dependency returns `User` consistently (Task 7 definition, Task 8 usage)
- `InvalidGoogleTokenError` exception class referenced in Tasks 5 (definition), 8 (catch)

**Scope check:** Sub-project A only. Sub-projects B/C/D explicitly deferred and called out where relevant (Task 13 step 13, spec references).
