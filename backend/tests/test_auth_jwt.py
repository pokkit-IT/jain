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
