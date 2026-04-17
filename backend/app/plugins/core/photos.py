"""Shared photo upload + thumbnail helpers for internal plugins.

Used by yardsailing (via yardsailing/photos.py) and custody (via
custody/photos.py). Each plugin binds these helpers to its own
ORM model and folder prefix.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
THUMB_MAX_DIM = 300


@dataclass
class SavedPhoto:
    """Result of a successful upload. Paths are relative to the uploads root."""
    original_path: str
    thumb_path: str
    content_type: str


def _ext_for(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[content_type]


def generate_thumbnail(src_path: str, dst_path: str) -> None:
    """Write a <=THUMB_MAX_DIM JPEG thumbnail at dst_path from the image at src_path."""
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        im.thumbnail((THUMB_MAX_DIM, THUMB_MAX_DIM))
        im.save(dst_path, "JPEG", quality=80)


async def save_upload(root: Path, sub_path: str, upload: UploadFile) -> SavedPhoto:
    """Persist an uploaded image under <root>/<sub_path>/. Generates a thumbnail.

    Raises HTTPException(400) on content-type mismatch, oversized file, or invalid image bytes.
    Returns paths relative to `root` with forward slashes (safe across OS).
    """
    content_type = (
        upload.headers.get("content-type") if hasattr(upload, "headers") else None
    ) or upload.content_type
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="unsupported_content_type")

    data = await upload.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="file_too_large")

    folder = root / sub_path
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

    return SavedPhoto(
        original_path=str(orig_abs.relative_to(root)).replace("\\", "/"),
        thumb_path=str(thumb_abs.relative_to(root)).replace("\\", "/"),
        content_type=content_type,
    )


def delete_files(root: Path, original_path: str, thumb_path: str) -> None:
    """Remove both the original and thumbnail file. Missing files are ignored."""
    (root / original_path).unlink(missing_ok=True)
    (root / thumb_path).unlink(missing_ok=True)
