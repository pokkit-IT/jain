# Yardsailing Sale Photos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a sale's host attach up to 5 photos per sale, displayed as a hero thumbnail in the list card and a full-size carousel in the sale details modal. Photos are added/managed after sale creation via a mobile-side sheet.

**Architecture:** New `SalePhoto` model (FK to `Sale` with cascade delete). Photos live on local filesystem under `uploads/sales/<sale_id>/`; Pillow generates ~300px JPEG thumbnails on upload; FastAPI `StaticFiles` mount serves both. Three endpoints (POST upload, DELETE photo, PATCH reorder) on the yardsailing router, all owner-authorized. Mobile: new `SalePhoto` type, three API client functions, a `ManagePhotosSheet` component reachable from `SaleDetailsModal` for owners, hero thumbnail in `DataCard`, carousel in `SaleDetailsModal`.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.0 async, Pillow, SQLite, pytest; React Native + Expo, TypeScript, expo-image-picker.

---

## Pre-flight notes

1. **Scope cut from spec:** Create-time photo upload from within `SaleForm` is deferred. `SaleForm` is in the plugin bundle (`backend/app/plugins/yardsailing/components/SaleForm.tsx`), which doesn't have a clean path to `expo-image-picker` without extending the PluginHost require shim. V1 does post-create only via `ManagePhotosSheet` in mobile core. A second pass can add create-time upload once a bridge method for image-pick exists.
2. **Uploads dir lives at `backend/uploads/`** (project-relative). Add to `.gitignore` so uploaded files aren't committed. Keep a `backend/uploads/.gitkeep`.
3. **Pillow supports JPEG/PNG/WebP out of the box.** HEIC coming from iOS is auto-converted by `expo-image-picker` to JPEG, so no `pillow-heif` dependency needed.
4. **Base URL for photo URLs.** Photo JSON returns relative URLs starting with `/uploads/...`; the mobile client prefixes with its API base (same pattern as other endpoints).

---

## Stage 1: Backend foundation

### Task 1: Add Pillow dependency, uploads dir, static mount

**Files:**
- Modify: `backend/pyproject.toml` (or `requirements.txt` — whichever the project uses; check first)
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/uploads/.gitkeep`
- Modify: `backend/.gitignore` (or root `.gitignore`)

- [ ] **Step 1: Inspect dependency file**

Run:
```bash
cd C:/Users/jimsh/repos/jain/backend
ls pyproject.toml requirements.txt 2>/dev/null
```

- [ ] **Step 2: Add Pillow**

If `pyproject.toml` exists with `[project.dependencies]` or `[tool.poetry.dependencies]`, add `"Pillow>=10.0"` there. Otherwise add to `requirements.txt`. Install:

```bash
cd C:/Users/jimsh/repos/jain/backend && pip install "Pillow>=10.0"
```

- [ ] **Step 3: Add UPLOADS_DIR to config**

Edit `backend/app/config.py`. Find the `Settings` class, add:

```python
UPLOADS_DIR: str = "uploads"  # project-relative, overridable via env
```

- [ ] **Step 4: Mount static directory**

Edit `backend/app/main.py`. Inside `create_app()` before routers are included, add:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

uploads_path = Path(settings.UPLOADS_DIR)
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")
```

- [ ] **Step 5: Create uploads dir + gitignore**

```bash
cd C:/Users/jimsh/repos/jain
mkdir -p backend/uploads && touch backend/uploads/.gitkeep
```

Edit `.gitignore` (root or backend/.gitignore — whichever the project uses). Add:

```
backend/uploads/*
!backend/uploads/.gitkeep
```

- [ ] **Step 6: Verify server starts**

Run (from `backend/`): `python -m pytest tests/test_health.py -v` — should still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py backend/app/main.py backend/uploads/.gitkeep .gitignore
git commit -m "feat(photos): Pillow dep, uploads static mount, UPLOADS_DIR config"
```

---

### Task 2: `SalePhoto` model

**Files:**
- Modify: `backend/app/plugins/yardsailing/models.py`
- Test: `backend/tests/plugins/yardsailing/test_models.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/plugins/yardsailing/test_models.py`:

```python
@pytest.mark.asyncio
async def test_sale_photo_created_and_linked(session_and_user):
    from app.plugins.yardsailing.models import Sale, SalePhoto
    from sqlalchemy import select
    import uuid

    session, user = session_and_user
    sale = Sale(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="t", address="a", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
        lat=0.0, lng=0.0,
    )
    session.add(sale)
    await session.flush()

    photo = SalePhoto(
        id=str(uuid.uuid4()),
        sale_id=sale.id,
        position=0,
        original_path=f"sales/{sale.id}/a.jpg",
        thumb_path=f"sales/{sale.id}/a-thumb.jpg",
        content_type="image/jpeg",
    )
    session.add(photo)
    await session.commit()

    res = await session.execute(select(SalePhoto).where(SalePhoto.sale_id == sale.id))
    loaded = res.scalar_one()
    assert loaded.position == 0
    assert loaded.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_deleting_sale_cascades_photos(session_and_user):
    from app.plugins.yardsailing.models import Sale, SalePhoto
    from sqlalchemy import select, delete
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
    session.add(SalePhoto(
        id=str(uuid.uuid4()), sale_id=sale_id, position=0,
        original_path="p", thumb_path="t", content_type="image/jpeg",
    ))
    await session.commit()

    await session.execute(delete(Sale).where(Sale.id == sale_id))
    await session.commit()

    res = await session.execute(select(SalePhoto).where(SalePhoto.sale_id == sale_id))
    assert res.scalars().all() == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_models.py -v`
Expected: ImportError on `SalePhoto`.

- [ ] **Step 3: Add model**

Edit `backend/app/plugins/yardsailing/models.py`. Append (adjust imports at top as needed — `datetime`, `Mapped`, `mapped_column`, `String`, `Integer`, `ForeignKey`, `DateTime` should already be present; add any missing):

```python
class SalePhoto(Base):
    __tablename__ = "yardsailing_sale_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sale_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("yardsailing_sales.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumb_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
```

Check the exact Sale table name in the file (likely `yardsailing_sales`) and match. Confirm `Base` is imported. Confirm the `ondelete="CASCADE"` works — SQLAlchemy's cascade at ORM level requires `relationship(cascade="all, delete-orphan")` on Sale. Add to `Sale`:

```python
# Inside Sale model class:
photos: Mapped[list["SalePhoto"]] = relationship(
    "SalePhoto",
    cascade="all, delete-orphan",
    order_by="SalePhoto.position",
)
```

If `relationship` is not already imported in the file, add `from sqlalchemy.orm import relationship` (or extend existing import).

- [ ] **Step 4: Ensure table creation picks up the new model**

`SalePhoto` is defined in the same module as `Sale`, so `create_all()` will find it as long as `models.py` is imported at startup. Confirm by checking the existing pattern in the plugin's `__init__.py` or loader wiring.

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_models.py -v`
Expected: both new tests PASS. If the cascade test fails, verify that SQLite pragma `foreign_keys=ON` is set (check `backend/app/database.py`). If not, the ORM relationship with `cascade="all, delete-orphan"` still covers the ORM path, but an explicit SQL-level delete will leave orphans — document that in a comment and rely on the ORM cascade.

- [ ] **Step 6: Commit**

```bash
git add backend/app/plugins/yardsailing/models.py backend/tests/plugins/yardsailing/test_models.py
git commit -m "feat(photos): SalePhoto model with cascade"
```

---

### Task 3: `photos.py` module

**Files:**
- Create: `backend/app/plugins/yardsailing/photos.py`
- Create: `backend/tests/plugins/yardsailing/test_photos_module.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/plugins/yardsailing/test_photos_module.py`:

```python
import io
from pathlib import Path

import pytest
from PIL import Image


def _jpeg_bytes(size=(1200, 900), color=(200, 100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_photos_module.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement module**

Create `backend/app/plugins/yardsailing/photos.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_photos_module.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/photos.py backend/tests/plugins/yardsailing/test_photos_module.py
git commit -m "feat(photos): save/delete/thumbnail helpers"
```

---

## Stage 2: Backend endpoints

### Task 4: `POST /photos` upload endpoint

**Files:**
- Modify: `backend/app/plugins/yardsailing/routes.py`
- Modify: `backend/tests/plugins/yardsailing/test_routes.py`

- [ ] **Step 1: Write failing test**

Append to `test_routes.py`:

```python
@pytest.mark.asyncio
async def test_upload_photo_endpoint_happy(app_and_token, seed_one_sale, tmp_path, monkeypatch):
    import io
    from PIL import Image
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    app, token = app_and_token
    sale_id = seed_one_sale
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (100, 200, 50)).save(buf, format="JPEG")
    buf.seek(0)

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos",
            files={"file": ("x.jpg", buf, "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["position"] == 0
    assert body["url"].startswith("/uploads/sales/")
    assert body["thumb_url"].startswith("/uploads/sales/")


@pytest.mark.asyncio
async def test_upload_photo_endpoint_non_owner_forbidden(app_and_token_two_users, seed_sale_for_user_a, tmp_path, monkeypatch):
    """User B cannot upload photos to User A's sale."""
    # ... full test — see details below
```

The exact fixture names (`app_and_token`, `seed_one_sale`, etc.) must match what already exists in `backend/tests/plugins/yardsailing/conftest.py`. **Read that conftest before writing tests**, and match names/signatures exactly. If a two-user fixture doesn't exist, add one:

```python
@pytest.fixture
async def app_and_token_two_users(app_and_token, test_db_session):
    """Returns (app, token_a, token_b, user_a_id, user_b_id)."""
    # Create second user + JWT; return both tokens.
    # Follow the existing pattern used by app_and_token.
```

For the full non-owner test, mirror the happy-path test, but have User B send the request against User A's `sale_id`, and assert `resp.status_code == 403`.

- [ ] **Step 2: Verify failing**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_routes.py::test_upload_photo_endpoint_happy -v`
Expected: 404 or similar.

- [ ] **Step 3: Add endpoint**

Edit `backend/app/plugins/yardsailing/routes.py`. Add (imports at top: `from fastapi import UploadFile, File`, `from .photos import save_photo, UPLOADS_ROOT`, and `from .models import SalePhoto`):

```python
def _photo_to_json(photo: SalePhoto) -> dict:
    return {
        "id": photo.id,
        "position": photo.position,
        "content_type": photo.content_type,
        "url": f"/uploads/{photo.original_path}",
        "thumb_url": f"/uploads/{photo.thumb_path}",
    }


@router.post("/sales/{sale_id}/photos")
async def upload_sale_photo(
    sale_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sale = await db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale_not_found")
    if sale.owner_id != user.id:
        raise HTTPException(status_code=403, detail="not_sale_owner")

    photo = await save_photo(db, sale_id, file)
    return _photo_to_json(photo)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_routes.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/routes.py backend/tests/plugins/yardsailing/test_routes.py backend/tests/plugins/yardsailing/conftest.py
git commit -m "feat(photos): POST /photos upload endpoint"
```

---

### Task 5: `DELETE /photos/{photo_id}` endpoint

**Files:**
- Modify: `backend/app/plugins/yardsailing/routes.py`
- Modify: `backend/tests/plugins/yardsailing/test_routes.py`

- [ ] **Step 1: Write failing test**

Append to `test_routes.py`:

```python
@pytest.mark.asyncio
async def test_delete_photo_endpoint(app_and_token, seed_one_sale_with_photo, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    app, token = app_and_token
    sale_id, photo_id, orig_rel, thumb_rel = seed_one_sale_with_photo

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos/{photo_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 204
    assert not (tmp_path / orig_rel).exists()
    assert not (tmp_path / thumb_rel).exists()
```

Add `seed_one_sale_with_photo` fixture in `conftest.py` that creates one sale and uploads one photo (reusing `save_photo`), returning the relevant IDs and relative paths.

- [ ] **Step 2: Verify failing**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_routes.py::test_delete_photo_endpoint -v`
Expected: 404.

- [ ] **Step 3: Add endpoint**

Append to `routes.py`:

```python
from fastapi import status


@router.delete("/sales/{sale_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale_photo(
    sale_id: str,
    photo_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.owner_id != user.id:
        raise HTTPException(status_code=404, detail="sale_not_found")
    photo = await db.get(SalePhoto, photo_id)
    if photo is None or photo.sale_id != sale_id:
        raise HTTPException(status_code=404, detail="photo_not_found")
    from .photos import delete_photo as _delete_photo
    await _delete_photo(db, photo)
    return None
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_routes.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/routes.py backend/tests/plugins/yardsailing/test_routes.py backend/tests/plugins/yardsailing/conftest.py
git commit -m "feat(photos): DELETE photo endpoint"
```

---

### Task 6: `PATCH /photos/reorder` endpoint

**Files:**
- Modify: `backend/app/plugins/yardsailing/routes.py`
- Modify: `backend/tests/plugins/yardsailing/test_routes.py`

- [ ] **Step 1: Write failing test**

Append to `test_routes.py`:

```python
@pytest.mark.asyncio
async def test_reorder_photos_endpoint(app_and_token, seed_one_sale_with_three_photos, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    app, token = app_and_token
    sale_id, ids = seed_one_sale_with_three_photos  # ids = [id0, id1, id2]
    reversed_ids = list(reversed(ids))

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.patch(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos/reorder",
            json={"photo_ids": reversed_ids},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert [p["id"] for p in body] == reversed_ids
    assert [p["position"] for p in body] == [0, 1, 2]


@pytest.mark.asyncio
async def test_reorder_rejects_mismatched_ids(app_and_token, seed_one_sale_with_three_photos):
    app, token = app_and_token
    sale_id, ids = seed_one_sale_with_three_photos

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.patch(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos/reorder",
            json={"photo_ids": ids[:2]},  # missing one
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
```

Add `seed_one_sale_with_three_photos` fixture that uploads three photos and returns `(sale_id, [id0, id1, id2])` in position order.

- [ ] **Step 2: Verify failing**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_routes.py::test_reorder_photos_endpoint -v`

- [ ] **Step 3: Add endpoint**

Append to `routes.py`:

```python
from pydantic import BaseModel


class ReorderRequest(BaseModel):
    photo_ids: list[str]


@router.patch("/sales/{sale_id}/photos/reorder")
async def reorder_sale_photos(
    sale_id: str,
    body: ReorderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.owner_id != user.id:
        raise HTTPException(status_code=404, detail="sale_not_found")

    from sqlalchemy import select
    res = await db.execute(select(SalePhoto).where(SalePhoto.sale_id == sale_id))
    existing = {p.id: p for p in res.scalars().all()}
    if set(existing.keys()) != set(body.photo_ids):
        raise HTTPException(status_code=400, detail="photo_ids_mismatch")

    for index, pid in enumerate(body.photo_ids):
        existing[pid].position = index
    await db.commit()

    return [
        _photo_to_json(existing[pid]) for pid in body.photo_ids
    ]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_routes.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/routes.py backend/tests/plugins/yardsailing/test_routes.py backend/tests/plugins/yardsailing/conftest.py
git commit -m "feat(photos): PATCH reorder endpoint"
```

---

### Task 7: Include `photos[]` in sale list/detail serialization

**Files:**
- Modify: `backend/app/plugins/yardsailing/services.py` (or wherever `list_recent_sales` / `get_sale_by_id` serialize)
- Modify: `backend/app/plugins/yardsailing/routes.py` (if serialization lives in routes)
- Modify: `backend/tests/plugins/yardsailing/test_routes.py`

- [ ] **Step 1: Identify where sales are serialized to JSON for the API**

Run:
```bash
cd C:/Users/jimsh/repos/jain
grep -rn "list_recent_sales\|def list_sales\|/sales" backend/app/plugins/yardsailing/ | head
```

Find the GET `/sales` and GET `/sales/{id}` handlers and the function that turns a `Sale` row into JSON. That's where we add `photos`.

- [ ] **Step 2: Write failing test**

Append to `test_routes.py`:

```python
@pytest.mark.asyncio
async def test_list_sales_includes_ordered_photos(app_and_token, seed_one_sale_with_three_photos, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    app, token = app_and_token
    sale_id, ids = seed_one_sale_with_three_photos

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get(
            "/api/plugins/yardsailing/sales",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    sales = resp.json()
    target = next(s for s in sales if s["id"] == sale_id)
    assert "photos" in target
    assert [p["id"] for p in target["photos"]] == ids
    assert target["photos"][0]["position"] == 0
    assert all("thumb_url" in p and "url" in p for p in target["photos"])
```

- [ ] **Step 3: Update serialization**

Where each `Sale` becomes a JSON dict (likely in `services.list_recent_sales` or a helper in `routes.py`), add:

```python
photos_sorted = sorted(s.photos or [], key=lambda p: p.position)
item["photos"] = [
    {
        "id": p.id,
        "position": p.position,
        "content_type": p.content_type,
        "url": f"/uploads/{p.original_path}",
        "thumb_url": f"/uploads/{p.thumb_path}",
    }
    for p in photos_sorted
]
```

If `list_recent_sales` uses a query that doesn't eagerly load photos, add `options(selectinload(Sale.photos))` to the query. Example:

```python
from sqlalchemy.orm import selectinload

q = select(Sale).options(selectinload(Sale.photos))
```

Also include `photos: SalePhoto[]` in any existing `SaleOut` pydantic schema, or if serialization is dict-based, just add the key.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/test_routes.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/services.py backend/app/plugins/yardsailing/routes.py backend/tests/plugins/yardsailing/test_routes.py
git commit -m "feat(photos): include photos array in sale listings"
```

---

### Task 8: Cascade folder cleanup on sale delete

**Files:**
- Modify: `backend/app/plugins/yardsailing/services.py` (where `delete_sale` or equivalent lives)
- Modify: `backend/tests/plugins/yardsailing/test_services.py`

- [ ] **Step 1: Write failing test**

Append to `test_services.py`:

```python
@pytest.mark.asyncio
async def test_delete_sale_removes_photos_folder(tmp_path, monkeypatch, session_and_user):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)

    import io
    from PIL import Image
    from fastapi import UploadFile
    from app.plugins.yardsailing.models import Sale
    from app.plugins.yardsailing.photos import save_photo, sale_folder
    from app.plugins.yardsailing.services import delete_sale
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

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (10, 10, 10)).save(buf, format="JPEG")
    buf.seek(0)
    file = UploadFile(filename="p.jpg", file=buf)
    file.headers = {"content-type": "image/jpeg"}  # type: ignore[attr-defined]
    await save_photo(session, sale.id, file)

    folder = sale_folder(sale.id)
    assert folder.exists()

    await delete_sale(session, user, sale.id)

    assert not folder.exists()
```

If the project has no `delete_sale` function yet, check how sales are deleted today (likely a DELETE endpoint calling `db.delete`). Either add `delete_sale(db, user, sale_id)` to `services.py` or modify the route handler directly. Pick whichever matches the existing pattern.

- [ ] **Step 2: Verify failing**

Run the new test.

- [ ] **Step 3: Add cascade**

Edit `services.py` (or route) — after deleting the sale row and committing, `shutil.rmtree(sale_folder(sale_id), ignore_errors=True)`:

```python
import shutil
from .photos import sale_folder

async def delete_sale(db, user, sale_id):
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.owner_id != user.id:
        raise HTTPException(status_code=404, detail="sale_not_found")
    await db.delete(sale)
    await db.commit()
    shutil.rmtree(sale_folder(sale_id), ignore_errors=True)
```

If the existing route inlines delete logic, keep the cascade in the route but call the helper `sale_folder(sale_id)` from `photos`.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/plugins/yardsailing/ -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/services.py backend/tests/plugins/yardsailing/test_services.py
git commit -m "feat(photos): cascade folder cleanup on sale delete"
```

---

## Stage 3: Mobile types and API

### Task 9: Mobile types and API client

**Files:**
- Modify: `mobile/src/types.ts`
- Modify: `mobile/src/api/yardsailing.ts`

- [ ] **Step 1: Extend `Sale` type**

Edit `mobile/src/types.ts`. Append:

```ts
export interface SalePhoto {
  id: string;
  position: number;
  content_type: string;
  url: string;       // relative, e.g. "/uploads/sales/<id>/<uuid>.jpg"
  thumb_url: string;
}
```

Add to the existing `Sale` interface:

```ts
  photos?: SalePhoto[];
```

- [ ] **Step 2: Add API client functions**

Edit `mobile/src/api/yardsailing.ts`. Append:

```ts
import type { SalePhoto } from "../types";

export async function uploadSalePhoto(
  saleId: string,
  file: { uri: string; name: string; type: string },
): Promise<SalePhoto> {
  const form = new FormData();
  // In RN, FormData.append with an object containing {uri, name, type}
  // is the canonical way to upload a local file.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form.append("file", file as any);
  const { data } = await apiClient.post<SalePhoto>(
    `/api/plugins/yardsailing/sales/${saleId}/photos`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function deleteSalePhoto(saleId: string, photoId: string): Promise<void> {
  await apiClient.delete(
    `/api/plugins/yardsailing/sales/${saleId}/photos/${photoId}`,
  );
}

export async function reorderSalePhotos(
  saleId: string,
  photoIds: string[],
): Promise<SalePhoto[]> {
  const { data } = await apiClient.patch<SalePhoto[]>(
    `/api/plugins/yardsailing/sales/${saleId}/photos/reorder`,
    { photo_ids: photoIds },
  );
  return data;
}
```

- [ ] **Step 3: tsc check**

Run: `cd mobile && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/types.ts mobile/src/api/yardsailing.ts
git commit -m "feat(mobile): SalePhoto type and photo API client"
```

---

## Stage 4: Mobile UI

### Task 10: Hero thumbnail in `DataCard` sale row

**Files:**
- Modify: `mobile/src/chat/DataCard.tsx`

- [ ] **Step 1: Verify base URL handling**

How does the app prefix relative server paths? Check `mobile/src/api/client.ts` for the axios `baseURL`. Assume it's something like `http://host:8000`. Mobile images need a fully qualified URL.

Decide: either compute absolute URL inline (`${apiBase}/uploads/...`), or add a helper `absUrl(path)` to `api/client.ts`. Pick the helper for reuse.

Add to `mobile/src/api/client.ts`:

```ts
export function absUrl(relative: string): string {
  if (/^https?:\/\//.test(relative)) return relative;
  return `${apiClient.defaults.baseURL}${relative}`;
}
```

(If baseURL ends in `/api`, strip it before concatenation. Inspect the existing export to get this right.)

- [ ] **Step 2: Render hero thumbnail**

Edit `DataCard.tsx`. Import `Image` from `react-native` and `absUrl` from `../api/client`.

In the existing `"map"` branch, inside each sale row (the `Pressable` for each card), just before the `View` containing the title/address, add:

```tsx
{sale.photos && sale.photos.length > 0 ? (
  <Image
    source={{ uri: absUrl(sale.photos[0].thumb_url) }}
    style={styles.hero}
  />
) : null}
```

Add style:

```ts
hero: {
  width: 56, height: 56, borderRadius: 8, marginRight: 10,
  backgroundColor: "#f1f5f9",
},
```

Ensure the row flex still works. The card is already `flexDirection: "row"` from the route-planner task.

- [ ] **Step 3: tsc + commit**

```bash
cd mobile && npx tsc --noEmit
cd .. && git add mobile/src/chat/DataCard.tsx mobile/src/api/client.ts
git commit -m "feat(mobile): hero thumbnail in sale list row"
```

---

### Task 11: Full-size carousel in `SaleDetailsModal`

**Files:**
- Modify: `mobile/src/core/SaleDetailsModal.tsx`

- [ ] **Step 1: Read the modal structure**

Read `mobile/src/core/SaleDetailsModal.tsx` to understand the existing layout.

- [ ] **Step 2: Add carousel**

Above the existing details section, when `sale?.photos?.length > 0`:

```tsx
{sale.photos && sale.photos.length > 0 ? (
  <ScrollView
    horizontal
    pagingEnabled
    showsHorizontalScrollIndicator={false}
    style={styles.carousel}
  >
    {sale.photos.map((p) => (
      <Image
        key={p.id}
        source={{ uri: absUrl(p.url) }}
        style={styles.carouselImage}
        resizeMode="cover"
      />
    ))}
  </ScrollView>
) : null}
```

Add styles:

```ts
carousel: { height: 240, marginBottom: 12 },
carouselImage: { width: Dimensions.get("window").width - 24, height: 240, borderRadius: 12, marginRight: 8 },
```

Import `Dimensions`, `ScrollView`, `Image` from `react-native` if not already. Import `absUrl` from `../api/client`.

- [ ] **Step 3: tsc + commit**

```bash
cd mobile && npx tsc --noEmit
cd .. && git add mobile/src/core/SaleDetailsModal.tsx
git commit -m "feat(mobile): photo carousel in sale details modal"
```

---

### Task 12: `ManagePhotosSheet` — add, remove, reorder (owner)

**Files:**
- Create: `mobile/src/core/ManagePhotosSheet.tsx`
- Modify: `mobile/src/core/SaleDetailsModal.tsx`

- [ ] **Step 1: Verify `expo-image-picker` is installed**

```bash
grep "expo-image-picker" C:/Users/jimsh/repos/jain/mobile/package.json
```

If missing:
```bash
cd C:/Users/jimsh/repos/jain/mobile && npx expo install expo-image-picker
```

- [ ] **Step 2: Check how "current user" is accessed on mobile**

```bash
grep -rn "currentUser\|useAuth\|useSession" mobile/src/ | head
```

Find the hook/selector that returns the logged-in user's ID. We need it to decide whether to show "Manage Photos."

- [ ] **Step 3: Create `ManagePhotosSheet.tsx`**

Create `mobile/src/core/ManagePhotosSheet.tsx`:

```tsx
import React from "react";
import {
  Image, Modal, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";

import { absUrl } from "../api/client";
import {
  uploadSalePhoto, deleteSalePhoto, reorderSalePhotos,
} from "../api/yardsailing";
import type { SalePhoto } from "../types";

interface Props {
  visible: boolean;
  saleId: string;
  photos: SalePhoto[];
  onClose: () => void;
  onChange: (photos: SalePhoto[]) => void;
}

const MAX = 5;

export function ManagePhotosSheet({ visible, saleId, photos, onClose, onChange }: Props) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const pick = async () => {
    if (photos.length >= MAX) return;
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) { setError("Photo library permission denied"); return; }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (res.canceled) return;
    setBusy(true); setError(null);
    try {
      const asset = res.assets[0];
      const uri = asset.uri;
      const name = asset.fileName ?? `photo-${Date.now()}.jpg`;
      const type = asset.mimeType ?? "image/jpeg";
      const uploaded = await uploadSalePhoto(saleId, { uri, name, type });
      onChange([...photos, uploaded]);
    } catch (e) {
      setError("Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (photoId: string) => {
    setBusy(true); setError(null);
    try {
      await deleteSalePhoto(saleId, photoId);
      onChange(photos.filter((p) => p.id !== photoId));
    } catch {
      setError("Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const move = async (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= photos.length) return;
    const newOrder = [...photos];
    const [moved] = newOrder.splice(index, 1);
    newOrder.splice(target, 0, moved);
    const ids = newOrder.map((p) => p.id);
    setBusy(true); setError(null);
    try {
      const updated = await reorderSalePhotos(saleId, ids);
      onChange(updated);
    } catch {
      setError("Reorder failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Manage Photos ({photos.length}/{MAX})</Text>
          <Pressable onPress={onClose}><Text style={styles.close}>Done</Text></Pressable>
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <ScrollView contentContainerStyle={styles.grid}>
          {photos.map((p, i) => (
            <View key={p.id} style={styles.tile}>
              <Image source={{ uri: absUrl(p.thumb_url) }} style={styles.thumb} />
              <View style={styles.tileActions}>
                <Pressable
                  style={[styles.tileBtn, i === 0 && styles.tileBtnDisabled]}
                  onPress={() => move(i, -1)}
                  disabled={i === 0 || busy}
                >
                  <Text style={styles.tileBtnText}>↑</Text>
                </Pressable>
                <Pressable
                  style={[styles.tileBtn, i === photos.length - 1 && styles.tileBtnDisabled]}
                  onPress={() => move(i, 1)}
                  disabled={i === photos.length - 1 || busy}
                >
                  <Text style={styles.tileBtnText}>↓</Text>
                </Pressable>
                <Pressable
                  style={styles.tileBtn}
                  onPress={() => remove(p.id)}
                  disabled={busy}
                >
                  <Text style={styles.tileBtnText}>✕</Text>
                </Pressable>
              </View>
            </View>
          ))}
          {photos.length < MAX ? (
            <Pressable
              style={[styles.tile, styles.addTile]}
              onPress={pick}
              disabled={busy}
            >
              <Text style={styles.addPlus}>+</Text>
              <Text style={styles.addLabel}>{busy ? "…" : "Add"}</Text>
            </Pressable>
          ) : null}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", paddingTop: 60 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16, borderBottomWidth: 1, borderBottomColor: "#e2e8f0" },
  title: { fontSize: 16, fontWeight: "700", color: "#0f172a" },
  close: { fontSize: 14, color: "#2563eb", fontWeight: "600" },
  error: { color: "#b91c1c", textAlign: "center", padding: 8, fontSize: 13 },
  grid: { flexDirection: "row", flexWrap: "wrap", padding: 12 },
  tile: { width: "31%", aspectRatio: 1, margin: "1%", borderRadius: 10, overflow: "hidden", backgroundColor: "#f1f5f9", position: "relative" },
  thumb: { width: "100%", height: "100%" },
  tileActions: { position: "absolute", bottom: 0, left: 0, right: 0, flexDirection: "row", justifyContent: "space-around", backgroundColor: "rgba(0,0,0,0.5)", paddingVertical: 4 },
  tileBtn: { paddingHorizontal: 6, paddingVertical: 2 },
  tileBtnDisabled: { opacity: 0.3 },
  tileBtnText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  addTile: { alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: "#cbd5e1", borderStyle: "dashed", backgroundColor: "#fff" },
  addPlus: { fontSize: 28, color: "#64748b" },
  addLabel: { fontSize: 11, color: "#64748b", marginTop: 2 },
});
```

- [ ] **Step 4: Wire into `SaleDetailsModal`**

Edit `mobile/src/core/SaleDetailsModal.tsx`. Add a "Manage Photos" button visible when current user owns the sale:

```tsx
import { ManagePhotosSheet } from "./ManagePhotosSheet";
// Import the current-user hook/selector you found in Step 2.

const [managing, setManaging] = React.useState(false);
const [localPhotos, setLocalPhotos] = React.useState(sale?.photos ?? []);
// Reset localPhotos when sale changes:
React.useEffect(() => { setLocalPhotos(sale?.photos ?? []); }, [sale?.id]);

const isOwner = currentUser?.id === sale?.owner_id;
```

Render the button and sheet:

```tsx
{isOwner ? (
  <Pressable onPress={() => setManaging(true)} style={styles.manageBtn}>
    <Text style={styles.manageBtnText}>Manage Photos</Text>
  </Pressable>
) : null}
{sale ? (
  <ManagePhotosSheet
    visible={managing}
    saleId={sale.id}
    photos={localPhotos}
    onClose={() => setManaging(false)}
    onChange={setLocalPhotos}
  />
) : null}
```

Also update the carousel from Task 11 to use `localPhotos` so the UI reacts to changes while the sheet is open.

Add styles:
```ts
manageBtn: { marginTop: 12, padding: 10, borderRadius: 8, borderWidth: 1, borderColor: "#2563eb", alignItems: "center" },
manageBtnText: { color: "#2563eb", fontWeight: "600", fontSize: 14 },
```

- [ ] **Step 5: tsc + commit**

```bash
cd mobile && npx tsc --noEmit
cd .. && git add mobile/src/core/ManagePhotosSheet.tsx mobile/src/core/SaleDetailsModal.tsx
git commit -m "feat(mobile): ManagePhotosSheet with add/remove/reorder"
```

---

## Stage 5: QA

### Task 13: Full test run and manual QA

- [ ] **Step 1: Backend**

```bash
cd C:/Users/jimsh/repos/jain/backend && python -m pytest -v
```
Expected: all tests PASS.

- [ ] **Step 2: Mobile tsc**

```bash
cd C:/Users/jimsh/repos/jain/mobile && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Manual QA** (user runs these on device/simulator)

- Create a sale. Open its details. Tap "Manage Photos."
- Add 3 photos one at a time; each appears and the count increments.
- Hit the add limit by adding 2 more (total 5); verify the "+" tile disappears.
- Reorder by tapping ↑/↓ arrows; verify carousel order updates.
- Delete one photo; verify it disappears from both sheet and carousel.
- Close the sheet; sale details modal shows updated carousel and `DataCard` list row shows updated hero thumbnail.
- Open the same sale as a different user; verify "Manage Photos" button is hidden.
- Delete the sale; verify the server folder `backend/uploads/sales/<id>/` is gone.
- Airplane-mode upload: verify "Upload failed" error appears and sheet stays responsive.

- [ ] **Step 4: Commit any fix-ups as separate commits**

---

## Out of scope (do not add)

- Create-time photo upload inside `SaleForm` (plugin bundle). Deferred until a bridge method for image-pick exists.
- Buyer/third-party uploads or moderation.
- EXIF/GPS stripping (Pillow strips EXIF on JPEG re-save for thumbnails only; originals keep it — acceptable for v1).
- Client-side compression.
- Zoom/pan in detail carousel.
- GCS/Drive storage migration.
- Drag-and-drop reorder (v2 — arrows for v1).
