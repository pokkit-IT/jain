from uuid import UUID

import jwt as pyjwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import verify_access_token
from app.database import get_db
from app.models.user import User


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Resolve the authenticated user from the Authorization header, or None.

    Unlike get_current_user, this dependency does NOT raise 401 on failure.
    Any invalid state (missing header, bad token, expired, deleted user)
    returns None so anonymous requests can continue.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None

    token = auth_header[7:]  # strip "Bearer " (7 chars)

    try:
        claims = verify_access_token(token)
    except pyjwt.PyJWTError:
        return None

    sub = claims.get("sub")
    if not sub:
        return None

    try:
        user_id = UUID(sub)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
