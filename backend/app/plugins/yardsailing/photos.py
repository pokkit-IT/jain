"""Photo storage and thumbnail generation for the yardsailing plugin.

Photos are written to <UPLOADS_ROOT>/sales/<sale_id>/<uuid>.<ext>.
Thumbnails are ~300 px JPEG siblings named <uuid>-thumb.jpg.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from .models import SalePhoto

MAX_PHOTOS_PER_SALE = 5
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
THUMB_MAX_DIM = 300

# Resolvable at import time so tests can monkeypatch.
UPLOADS_ROOT: Path = Path(settings.UPLOADS_DIR)


def sale_folder(sale_id: str) -> Path:
    return UPLOADS_ROOT / "sales" / sale_id


def generate_thumbnail(src_path: str, dst_path: str) -> None:
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        im.thumbnail((THUMB_MAX_DIM, THUMB_MAX_DIM))
        im.save(dst_path, "JPEG", quality=80)


def _ext_for(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[content_type]


async def save_photo(db: AsyncSession, sale_id: str, upload: UploadFile) -> SalePhoto:
    content_type = (upload.headers.get("content-type") if hasattr(upload, "headers") else None) or upload.content_type
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="unsupported_content_type")

    data = await upload.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="file_too_large")

    count_res = await db.execute(
        select(func.count(SalePhoto.id)).where(SalePhoto.sale_id == sale_id)
    )
    existing = count_res.scalar_one()
    if existing >= MAX_PHOTOS_PER_SALE:
        raise HTTPException(status_code=400, detail="too_many_photos")

    folder = sale_folder(sale_id)
    folder.mkdir(parents=True, exist_ok=True)

    photo_uuid = uuid.uuid4().hex
    ext = _ext_for(content_type)
    orig_abs = folder / f"{photo_uuid}.{ext}"
    thumb_abs = folder / f"{photo_uuid}-thumb.jpg"

    orig_abs.write_bytes(data)
    try:
        generate_thumbnail(str(orig_abs), str(thumb_abs))
    except Exception:
        orig_abs.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="invalid_image")

    photo = SalePhoto(
        id=str(uuid.uuid4()),
        sale_id=sale_id,
        position=existing,
        original_path=str(orig_abs.relative_to(UPLOADS_ROOT)).replace("\\", "/"),
        thumb_path=str(thumb_abs.relative_to(UPLOADS_ROOT)).replace("\\", "/"),
        content_type=content_type,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


async def delete_photo(db: AsyncSession, photo: SalePhoto) -> None:
    orig = UPLOADS_ROOT / photo.original_path
    thumb = UPLOADS_ROOT / photo.thumb_path
    orig.unlink(missing_ok=True)
    thumb.unlink(missing_ok=True)
    await db.delete(photo)
    await db.commit()
