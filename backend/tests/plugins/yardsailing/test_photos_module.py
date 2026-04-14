import io
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


def _jpeg_bytes(size=(1200, 900), color=(200, 100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        yield s, user
    await engine.dispose()


def test_generate_thumbnail_smaller_than_source(tmp_path):
    from app.plugins.yardsailing.photos import generate_thumbnail

    src = tmp_path / "src.jpg"
    dst = tmp_path / "dst.jpg"
    src.write_bytes(_jpeg_bytes())

    generate_thumbnail(str(src), str(dst))

    assert dst.exists()
    assert dst.stat().st_size < src.stat().st_size
    with Image.open(dst) as im:
        w, h = im.size
        assert max(w, h) <= 300


def test_sale_folder_is_under_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    from app.plugins.yardsailing.photos import sale_folder

    p = sale_folder("abc-123")
    assert p == tmp_path / "sales" / "abc-123"


@pytest.mark.asyncio
async def test_save_photo_happy_path(tmp_path, monkeypatch, session_and_user):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    from fastapi import UploadFile
    from app.plugins.yardsailing.models import Sale
    from app.plugins.yardsailing.photos import save_photo
    import uuid

    session, user = session_and_user
    sale = Sale(
        id=str(uuid.uuid4()), owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    await session.commit()

    file = UploadFile(filename="pic.jpg", file=io.BytesIO(_jpeg_bytes()))
    file.headers = {"content-type": "image/jpeg"}  # type: ignore[attr-defined]

    photo = await save_photo(session, sale.id, file)

    assert photo.position == 0
    assert photo.content_type == "image/jpeg"
    assert (tmp_path / photo.original_path).exists()
    assert (tmp_path / photo.thumb_path).exists()


@pytest.mark.asyncio
async def test_save_photo_rejects_non_image(tmp_path, monkeypatch, session_and_user):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    from fastapi import UploadFile, HTTPException
    from app.plugins.yardsailing.models import Sale
    from app.plugins.yardsailing.photos import save_photo
    import uuid

    session, user = session_and_user
    sale = Sale(
        id=str(uuid.uuid4()), owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    await session.commit()

    file = UploadFile(filename="bad.txt", file=io.BytesIO(b"hello"))
    file.headers = {"content-type": "text/plain"}  # type: ignore[attr-defined]

    with pytest.raises(HTTPException) as exc:
        await save_photo(session, sale.id, file)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_save_photo_rejects_over_cap(tmp_path, monkeypatch, session_and_user):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    from fastapi import UploadFile, HTTPException
    from app.plugins.yardsailing.models import Sale, SalePhoto
    from app.plugins.yardsailing.photos import save_photo, MAX_PHOTOS_PER_SALE
    import uuid

    session, user = session_and_user
    sale_id = str(uuid.uuid4())
    session.add(Sale(
        id=sale_id, owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    ))
    for i in range(MAX_PHOTOS_PER_SALE):
        session.add(SalePhoto(
            id=str(uuid.uuid4()), sale_id=sale_id, position=i,
            original_path=f"x{i}", thumb_path=f"t{i}", content_type="image/jpeg",
        ))
    await session.commit()

    file = UploadFile(filename="pic.jpg", file=io.BytesIO(_jpeg_bytes()))
    file.headers = {"content-type": "image/jpeg"}  # type: ignore[attr-defined]

    with pytest.raises(HTTPException) as exc:
        await save_photo(session, sale_id, file)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_photo_removes_files_and_row(tmp_path, monkeypatch, session_and_user):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    from fastapi import UploadFile
    from app.plugins.yardsailing.models import Sale, SalePhoto
    from app.plugins.yardsailing.photos import save_photo, delete_photo
    from sqlalchemy import select
    import uuid

    session, user = session_and_user
    sale = Sale(
        id=str(uuid.uuid4()), owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    await session.commit()

    file = UploadFile(filename="pic.jpg", file=io.BytesIO(_jpeg_bytes()))
    file.headers = {"content-type": "image/jpeg"}  # type: ignore[attr-defined]
    photo = await save_photo(session, sale.id, file)
    orig = tmp_path / photo.original_path
    thumb = tmp_path / photo.thumb_path
    assert orig.exists() and thumb.exists()

    await delete_photo(session, photo)

    assert not orig.exists() and not thumb.exists()
    res = await session.execute(select(SalePhoto).where(SalePhoto.id == photo.id))
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_save_photo_cleans_up_files_if_commit_fails(tmp_path, monkeypatch, session_and_user):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    import io
    from fastapi import UploadFile
    from app.plugins.yardsailing.models import Sale
    from app.plugins.yardsailing.photos import save_photo, sale_folder
    import uuid

    session, user = session_and_user
    sale = Sale(
        id=str(uuid.uuid4()), owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    await session.commit()

    # Force commit to fail by monkeypatching session.commit AFTER the first commit above.
    async def failing_commit():
        raise RuntimeError("simulated commit failure")
    monkeypatch.setattr(session, "commit", failing_commit)

    file = UploadFile(filename="pic.jpg", file=io.BytesIO(_jpeg_bytes()))
    file.headers = {"content-type": "image/jpeg"}  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError):
        await save_photo(session, sale.id, file)

    # Neither files should exist — both must have been cleaned up.
    folder = sale_folder(sale.id)
    if folder.exists():
        assert list(folder.iterdir()) == []
