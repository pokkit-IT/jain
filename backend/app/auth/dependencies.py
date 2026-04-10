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
