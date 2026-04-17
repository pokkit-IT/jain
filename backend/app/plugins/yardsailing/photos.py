"""Photo storage helpers for the yardsailing plugin.

File I/O and thumbnail logic delegates to app.plugins.core.photos.
This module handles yardsailing-specific concerns: per-sale photo cap,
SalePhoto ORM persistence, and DB cleanup on commit failure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.plugins.core.photos import (
    MAX_BYTES,  # re-exported for backwards compatibility
    ALLOWED_TYPES,  # re-exported for backwards compatibility
    THUMB_MAX_DIM,  # re-exported for backwards compatibility
    generate_thumbnail,  # re-exported; tests import directly from here
    save_upload as _core_save_upload,
    delete_files as _core_delete_files,
)

from .models import SalePhoto

MAX_PHOTOS_PER_SALE = 5

# Resolvable at import time so tests can monkeypatch.
UPLOADS_ROOT: Path = Path(settings.UPLOADS_DIR)


def sale_folder(sale_id: str) -> Path:
    return UPLOADS_ROOT / "sales" / sale_id


async def save_photo(db: AsyncSession, sale_id: str, upload: UploadFile) -> SalePhoto:
    count_res = await db.execute(
        select(func.count(SalePhoto.id)).where(SalePhoto.sale_id == sale_id)
    )
    existing = count_res.scalar_one()
    if existing >= MAX_PHOTOS_PER_SALE:
        raise HTTPException(status_code=400, detail="too_many_photos")

    saved = await _core_save_upload(UPLOADS_ROOT, f"sales/{sale_id}", upload)

    photo = SalePhoto(
        id=str(uuid.uuid4()),
        sale_id=sale_id,
        position=existing,
        original_path=saved.original_path,
        thumb_path=saved.thumb_path,
        content_type=saved.content_type,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(photo)
    try:
        await db.commit()
    except Exception:
        _core_delete_files(UPLOADS_ROOT, saved.original_path, saved.thumb_path)
        raise
    await db.refresh(photo)
    return photo


async def delete_photo(db: AsyncSession, photo: SalePhoto) -> None:
    _core_delete_files(UPLOADS_ROOT, photo.original_path, photo.thumb_path)
    await db.delete(photo)
    await db.commit()
