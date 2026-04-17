from sqlalchemy.ext.asyncio import create_async_engine

from app.models.base import Base


async def test_all_nutrition_tables_created():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.nutrition import models as _m  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        names = await conn.run_sync(
            lambda c: {
                r[0]
                for r in c.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        )
    await engine.dispose()

    assert {
        "nutrition_user_profiles",
        "nutrition_foods",
        "nutrition_meals",
        "nutrition_meal_items",
        "nutrition_day_summaries",
    }.issubset(names)


async def test_apply_dev_migrations_is_idempotent():
    from app.database import _apply_dev_migrations
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.nutrition import models as _m  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_dev_migrations(conn)
        await _apply_dev_migrations(conn)
    await engine.dispose()
