"""Thin binding around app.plugins.core.photos for custody event photos.

Uploads live at <UPLOADS_ROOT>/custody/<event_id>/<uuid>.<ext>.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.plugins.core.photos import delete_files, save_upload

from .models import EventPhoto

MAX_PHOTOS_PER_EVENT = 5

UPLOADS_ROOT: Path = Path(settings.UPLOADS_DIR)


def event_folder(event_id: str) -> Path:
    return UPLOADS_ROOT / "custody" / event_id


async def save_event_photo(
    db: AsyncSession, event_id: str, upload: UploadFile,
) -> EventPhoto:
    count_res = await db.execute(
        select(func.count(EventPhoto.id)).where(EventPhoto.event_id == event_id)
    )
    existing = count_res.scalar_one()
    if existing >= MAX_PHOTOS_PER_EVENT:
        raise HTTPException(status_code=400, detail="too_many_photos")

    saved = await save_upload(UPLOADS_ROOT, f"custody/{event_id}", upload)

    photo = EventPhoto(
        id=str(uuid.uuid4()),
        event_id=event_id,
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
        delete_files(UPLOADS_ROOT, saved.original_path, saved.thumb_path)
        raise
    await db.refresh(photo)
    return photo


async def delete_event_photo(db: AsyncSession, photo: EventPhoto) -> None:
    delete_files(UPLOADS_ROOT, photo.original_path, photo.thumb_path)
    await db.delete(photo)
    await db.commit()
