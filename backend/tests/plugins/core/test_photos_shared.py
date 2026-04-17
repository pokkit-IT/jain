# backend/tests/plugins/core/test_photos_shared.py
import io
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from PIL import Image

from app.plugins.core.photos import (
    ALLOWED_TYPES,
    MAX_BYTES,
    THUMB_MAX_DIM,
    SavedPhoto,
    delete_files,
    generate_thumbnail,
    save_upload,
)


def _make_upload(data: bytes, content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(
        filename="x.jpg",
        file=io.BytesIO(data),
        headers=Headers({"content-type": content_type}),
    )


def _jpeg_bytes(w: int = 100, h: int = 100) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color=(200, 50, 50)).save(buf, "JPEG")
    return buf.getvalue()


def test_constants_exposed():
    assert MAX_BYTES == 10 * 1024 * 1024
    assert "image/jpeg" in ALLOWED_TYPES
    assert THUMB_MAX_DIM == 300


@pytest.mark.asyncio
async def test_save_upload_writes_original_and_thumb(tmp_path: Path):
    saved = await save_upload(tmp_path, "sub/abc", _make_upload(_jpeg_bytes()))
    assert isinstance(saved, SavedPhoto)
    assert (tmp_path / saved.original_path).exists()
    assert (tmp_path / saved.thumb_path).exists()
    assert saved.content_type == "image/jpeg"
    assert saved.original_path.startswith("sub/abc/")
    assert saved.thumb_path.endswith("-thumb.jpg")


@pytest.mark.asyncio
async def test_save_upload_rejects_bad_type(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        await save_upload(tmp_path, "sub/abc", _make_upload(b"xx", "application/pdf"))
    assert exc.value.status_code == 400
    assert exc.value.detail == "unsupported_content_type"


@pytest.mark.asyncio
async def test_save_upload_rejects_oversize(tmp_path: Path):
    big = b"0" * (MAX_BYTES + 1)
    with pytest.raises(HTTPException) as exc:
        await save_upload(tmp_path, "sub/abc", _make_upload(big))
    assert exc.value.status_code == 400
    assert exc.value.detail == "file_too_large"


def test_generate_thumbnail_shrinks(tmp_path: Path):
    src = tmp_path / "big.jpg"
    src.write_bytes(_jpeg_bytes(1200, 900))
    dst = tmp_path / "small.jpg"
    generate_thumbnail(str(src), str(dst))
    with Image.open(dst) as im:
        assert max(im.size) <= THUMB_MAX_DIM


def test_delete_files_removes_both(tmp_path: Path):
    o = tmp_path / "a.jpg"
    t = tmp_path / "a-thumb.jpg"
    o.write_bytes(b"x")
    t.write_bytes(b"y")
    delete_files(tmp_path, "a.jpg", "a-thumb.jpg")
    assert not o.exists()
    assert not t.exists()
