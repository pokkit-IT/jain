from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .models.base import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_dev_migrations(conn)


async def _apply_dev_migrations(conn) -> None:
    """Tiny idempotent column-adds for SQLite dev DBs.

    create_all() creates missing tables but never adds columns to existing
    ones. For single-user dev with no Alembic, this patches in new columns
    so schema changes don't require deleting jain.db.
    """
    from sqlalchemy import text

    def _columns(sync_conn, table: str) -> set[str]:
        rows = sync_conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}

    def _table_exists(sync_conn, table: str) -> bool:
        row = sync_conn.exec_driver_sql(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
        ).fetchone()
        return row is not None

    wants = [
        ("yardsailing_sales", "lat", "REAL"),
        ("yardsailing_sales", "lng", "REAL"),
    ]
    for table, col, coltype in wants:
        if not await conn.run_sync(_table_exists, table):
            continue
        cols = await conn.run_sync(_columns, table)
        if col not in cols:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
