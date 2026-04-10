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

    result = await db.execute(
        select(User).where(User.google_sub == claims.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
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
