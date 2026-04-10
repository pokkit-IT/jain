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
        jwt.MissingRequiredClaimError: token is missing sub/exp/iat
        jwt.InvalidTokenError: other validation failures
    """
    return pyjwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "exp", "iat"]},
    )
