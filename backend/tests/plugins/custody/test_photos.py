import io
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (0, 200, 0)).save(buf, "JPEG")
    return buf.getvalue()


def _make_upload(data: bytes, content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(
        filename="x.jpg",
        file=io.BytesIO(data),
        headers=Headers({"content-type": content_type}),
    )


@pytest.fixture
async def session_with_event(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.plugins.custody.photos.UPLOADS_ROOT", tmp_path, raising=False,
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import (
            CreateEventInput, create_child, create_event,
        )
        from datetime import datetime
        child = await create_child(s, user, name="Mason")
        evt = await create_event(s, user, CreateEventInput(
            child_id=child.id, type="expense",
            occurred_at=datetime(2026, 1, 2, 12, 0),
            amount_cents=100, category="food",
        ))
        yield s, evt, tmp_path
    await engine.dispose()


@pytest.mark.asyncio
async def test_save_photo_writes_files_and_db(session_with_event):
    from app.plugins.custody.photos import save_event_photo
    from app.plugins.custody.models import EventPhoto
    from sqlalchemy import select

    s, evt, root = session_with_event
    photo = await save_event_photo(s, evt.id, _make_upload(_jpeg_bytes()))
    assert photo.event_id == evt.id
    assert (root / photo.original_path).exists()
    assert (root / photo.thumb_path).exists()

    res = await s.execute(select(EventPhoto).where(EventPhoto.event_id == evt.id))
    assert len(list(res.scalars().all())) == 1


@pytest.mark.asyncio
async def test_save_photo_enforces_five_per_event(session_with_event):
    from app.plugins.custody.photos import save_event_photo

    s, evt, _ = session_with_event
    for _ in range(5):
        await save_event_photo(s, evt.id, _make_upload(_jpeg_bytes()))
    with pytest.raises(HTTPException) as exc:
        await save_event_photo(s, evt.id, _make_upload(_jpeg_bytes()))
    assert exc.value.detail == "too_many_photos"


@pytest.mark.asyncio
async def test_delete_event_photo_removes_files(session_with_event):
    from app.plugins.custody.photos import delete_event_photo, save_event_photo
    from app.plugins.custody.models import EventPhoto
    from sqlalchemy import select

    s, evt, root = session_with_event
    photo = await save_event_photo(s, evt.id, _make_upload(_jpeg_bytes()))
    orig = root / photo.original_path
    await delete_event_photo(s, photo)
    assert not orig.exists()
    res = await s.execute(select(EventPhoto).where(EventPhoto.id == photo.id))
    assert res.scalar_one_or_none() is None
