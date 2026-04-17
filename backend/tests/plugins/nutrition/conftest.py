from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_and_user():
    """Fresh in-memory DB + a single User. Yields (session, user)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Import all model modules so metadata is complete before create_all.
        from app.plugins.nutrition import models as _nutrition_models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid4(),
            email="nutri@test.com",
            name="N",
            email_verified=True,
            google_sub="g-nutri",
        )
        s.add(user)
        await s.commit()
        yield s, user
    await engine.dispose()
