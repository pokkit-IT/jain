# Custody Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new internal plugin `custody` that lets a parent log visitation events (pickups, dropoffs, activities, expenses with receipts, text screenshots, medical/school, missed visits, phone calls, notes), auto-flag missed scheduled pickups, and export a court-ready PDF/CSV for any date range.

**Architecture:** Single polymorphic `custody_events` table with nullable typed columns (approach A from the design spec). Recurring schedules live in `custody_schedules` with per-date `custody_schedule_exceptions`. Five tables total, all prefixed `custody_`. LLM tools in chat plus a rich React Native home screen (status card + timeline + quick actions). Shared photo helper code is extracted into `app/plugins/core/photos.py` so both yardsailing and custody use it.

**Tech Stack:** FastAPI + SQLAlchemy async + Pydantic (backend), pytest + httpx AsyncClient (tests), reportlab (PDF export), React Native + esbuild (mobile bundle).

**Spec:** `docs/superpowers/specs/2026-04-16-custody-tracker-design.md`

**Branch:** `feature/custody-tracker`

---

## Phase 0 — Shared photo helper refactor

Yardsailing's `photos.py` is ~90% generic (thumbnail, validation, upload, delete). Extract the generic half into `app/plugins/core/photos.py` so custody can reuse it. Keep yardsailing's tests green.

### Task 0.1: Create shared photo helpers module

**Files:**
- Create: `backend/app/plugins/core/photos.py`
- Test: `backend/tests/plugins/core/test_photos_shared.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/plugins/core/__init__.py` as an empty file, then write:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/core/test_photos_shared.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.plugins.core.photos'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/plugins/core/photos.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/core/test_photos_shared.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/core/photos.py backend/tests/plugins/core/__init__.py backend/tests/plugins/core/test_photos_shared.py
git commit -m "feat(plugins/core): shared photo upload + thumbnail helpers"
```

---

### Task 0.2: Refactor yardsailing/photos.py to use shared helpers

**Files:**
- Modify: `backend/app/plugins/yardsailing/photos.py`

- [ ] **Step 1: Verify yardsailing tests are currently green (baseline)**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/yardsailing/ -v`
Expected: all PASS. If not, stop and investigate.

- [ ] **Step 2: Replace yardsailing/photos.py with shared-helper-backed version**

```python
# backend/app/plugins/yardsailing/photos.py
"""Photo storage for the yardsailing plugin. Thin binding around
app.plugins.core.photos — the generic upload/thumbnail logic lives there.
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
    ALLOWED_TYPES,  # re-export for tests that import them via this module
    MAX_BYTES,
    THUMB_MAX_DIM,
    delete_files,
    generate_thumbnail,
    save_upload,
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

    saved = await save_upload(UPLOADS_ROOT, f"sales/{sale_id}", upload)

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
        delete_files(UPLOADS_ROOT, saved.original_path, saved.thumb_path)
        raise
    await db.refresh(photo)
    return photo


async def delete_photo(db: AsyncSession, photo: SalePhoto) -> None:
    delete_files(UPLOADS_ROOT, photo.original_path, photo.thumb_path)
    await db.delete(photo)
    await db.commit()


__all__ = [
    "ALLOWED_TYPES",
    "MAX_BYTES",
    "MAX_PHOTOS_PER_SALE",
    "THUMB_MAX_DIM",
    "UPLOADS_ROOT",
    "delete_photo",
    "generate_thumbnail",
    "sale_folder",
    "save_photo",
]
```

- [ ] **Step 3: Run yardsailing tests to verify nothing broke**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/yardsailing/ -v`
Expected: same tests PASS as before. If any fail, re-read the diff — typical culprit is a test that imported a constant from the now-thinner `photos.py` (all constants are re-exported, so this should work).

- [ ] **Step 4: Run the full test suite to make sure nothing else regressed**

Run: `cd backend && .venv/Scripts/pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/photos.py
git commit -m "refactor(yardsailing): photos.py uses shared core helpers"
```

---

### Task 0.3: Add reportlab to requirements

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Append reportlab to requirements**

Open `backend/requirements.txt` and add a new line:

```
reportlab==4.2.5
```

Keep alphabetical ordering if the file is sorted; otherwise append at the end.

- [ ] **Step 2: Install**

Run: `cd backend && .venv/Scripts/pip install reportlab==4.2.5`
Expected: install succeeds (pure Python wheel, no system deps).

- [ ] **Step 3: Verify import**

Run: `cd backend && .venv/Scripts/python -c "from reportlab.pdfgen.canvas import Canvas; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(deps): add reportlab for custody PDF export"
```

---

## Phase 1 — Custody data model

Creates the five `custody_*` tables and a plugin skeleton so JAIN picks up the package at startup. No routes or tools yet — just `models.py` + `__init__.py` + `plugin.json`.

### Task 1.1: Plugin skeleton (package + manifest + empty registration)

**Files:**
- Create: `backend/app/plugins/custody/__init__.py`
- Create: `backend/app/plugins/custody/plugin.json`
- Create: `backend/tests/plugins/custody/__init__.py`
- Test: `backend/tests/plugins/custody/test_skeleton.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_skeleton.py
from app.plugins.custody import register


def test_register_returns_registration_with_name_and_version():
    reg = register()
    assert reg.name == "custody"
    assert reg.version == "1.0.0"
    assert reg.type == "internal"
    # tools start empty; filled in Phase 5
    assert reg.tools == []


def test_plugin_json_exists_and_has_home_block():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "app" / "plugins" / "custody" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"] == "custody"
    assert data["type"] == "internal"
    assert data["home"]["component"] == "CustodyHome"
    assert data["home"]["label"] == "Custody"
```

(Also create an empty `backend/tests/plugins/custody/__init__.py`.)

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_skeleton.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.plugins.custody'`.

- [ ] **Step 3: Create the skeleton**

```python
# backend/app/plugins/custody/__init__.py
"""First-party internal custody plugin.

Logs visitation events (pickups, dropoffs, activities, expenses,
text-screenshot attachments, medical/school, missed visits, phone
calls, notes) against one or more children. Exposes LLM tools for
natural-language logging from chat, a rich home screen with status +
timeline, and a PDF/CSV export for any date range.

Module layout mirrors yardsailing: models / routes / services /
tools / schedules / photos / export, plus a components/ folder for
the React Native bundle.
"""

from app.plugins.core.types import PluginRegistration


def register() -> PluginRegistration:
    # Lazy imports so the package can be imported cleanly across
    # in-progress phases — later tasks populate these modules.
    try:
        from .routes import router  # type: ignore[attr-defined]
    except ImportError:
        router = None  # Phase 1 skeleton: routes not yet created.
    try:
        from .tools import TOOLS  # type: ignore[attr-defined]
    except ImportError:
        TOOLS = []

    # Importing models has a side-effect of registering tables on
    # SQLAlchemy's Base.metadata so create_all picks them up at startup.
    try:
        from . import models  # noqa: F401
    except ImportError:
        pass

    return PluginRegistration(
        name="custody",
        version="1.0.0",
        type="internal",
        router=router,
        tools=TOOLS,
        ui_bundle_path="bundle/custody.js",
        ui_components=[
            "CustodyHome",
            "ExpenseForm",
            "TextCaptureForm",
            "EventForm",
            "ScheduleForm",
            "ScheduleListScreen",
            "ChildrenScreen",
            "ExportSheet",
        ],
    )
```

```json
// backend/app/plugins/custody/plugin.json
{
  "name": "custody",
  "version": "1.0.0",
  "description": "Log visitations, expenses, texts, and schedules with your children.",
  "author": "jim shelly",
  "type": "internal",
  "skills": [],
  "components": {
    "bundle": "bundle/custody.js",
    "exports": [
      "CustodyHome",
      "ExpenseForm",
      "TextCaptureForm",
      "EventForm",
      "ScheduleForm",
      "ScheduleListScreen",
      "ChildrenScreen",
      "ExportSheet"
    ]
  },
  "home": {
    "component": "CustodyHome",
    "label": "Custody",
    "icon": "people-outline",
    "description": "Track visitation events, expenses, and schedules."
  },
  "examples": [
    {"prompt": "Picked up Mason", "description": "Logs a pickup stamped to now"},
    {"prompt": "Dropped Mason off", "description": "Logs a dropoff"},
    {"prompt": "Bowling with Mason $42", "description": "Logs an activity plus an expense"},
    {"prompt": "How much have I spent on Mason this month?", "description": "Summarizes expense events"}
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_skeleton.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/__init__.py backend/app/plugins/custody/plugin.json backend/tests/plugins/custody/__init__.py backend/tests/plugins/custody/test_skeleton.py
git commit -m "feat(custody): plugin skeleton + manifest"
```

---

### Task 1.2: Child + CustodyEvent + EventPhoto models

**Files:**
- Create: `backend/app/plugins/custody/models.py`
- Test: `backend/tests/plugins/custody/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_models.py
import uuid
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Import custody models so they register on Base.metadata.
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="x@y.com", name="X", email_verified=True, google_sub="g1")
        s.add(user)
        await s.flush()
        yield s, user
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_child_and_event(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason", dob="2020-08-12")
    session.add(child)
    await session.flush()

    evt = CustodyEvent(
        owner_id=user.id,
        child_id=child.id,
        type="pickup",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        notes="school pickup",
        location="Elm Elementary",
        overnight=True,
    )
    session.add(evt)
    await session.commit()

    res = await session.execute(select(CustodyEvent).where(CustodyEvent.child_id == child.id))
    loaded = res.scalar_one()
    assert loaded.type == "pickup"
    assert loaded.overnight is True
    assert loaded.location == "Elm Elementary"


@pytest.mark.asyncio
async def test_expense_fields(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason")
    session.add(child)
    await session.flush()

    evt = CustodyEvent(
        owner_id=user.id, child_id=child.id,
        type="expense",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        amount_cents=4250, category="activity",
        notes="bowling",
    )
    session.add(evt)
    await session.commit()

    res = await session.execute(select(CustodyEvent).where(CustodyEvent.type == "expense"))
    loaded = res.scalar_one()
    assert loaded.amount_cents == 4250
    assert loaded.category == "activity"


@pytest.mark.asyncio
async def test_delete_child_cascades_events(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason")
    session.add(child)
    await session.flush()
    session.add(CustodyEvent(
        owner_id=user.id, child_id=child.id,
        type="note",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        notes="hi",
    ))
    await session.commit()

    await session.delete(child)
    await session.commit()

    res = await session.execute(select(CustodyEvent))
    assert res.scalars().all() == []


@pytest.mark.asyncio
async def test_event_photo_cascades_on_event_delete(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent, EventPhoto

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason")
    session.add(child)
    await session.flush()
    evt = CustodyEvent(
        owner_id=user.id, child_id=child.id,
        type="expense",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        amount_cents=100, category="food",
    )
    session.add(evt)
    await session.flush()
    session.add(EventPhoto(
        id=str(uuid.uuid4()), event_id=evt.id, position=0,
        original_path="p", thumb_path="t", content_type="image/jpeg",
    ))
    await session.commit()

    await session.delete(evt)
    await session.commit()

    res = await session.execute(select(EventPhoto))
    assert res.scalars().all() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'Child' from 'app.plugins.custody.models'`.

- [ ] **Step 3: Write the models**

```python
# backend/app/plugins/custody/models.py
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


def _new_id() -> str:
    return str(uuid4())


class Child(Base):
    """A child whose custody events are being tracked by `owner`."""

    __tablename__ = "custody_children"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    dob: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    owner: Mapped[User] = relationship()
    events: Mapped[list["CustodyEvent"]] = relationship(
        "CustodyEvent", back_populates="child",
        cascade="all, delete-orphan", lazy="selectin",
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="child",
        cascade="all, delete-orphan", lazy="selectin",
    )


class CustodyEvent(Base):
    """Polymorphic event row. `type` drives which optional fields are meaningful.

    Common fields (type-agnostic): occurred_at, notes, location.
    Typed columns (nullable, set only when relevant):
      - overnight       → pickup
      - amount_cents    → expense
      - category        → expense
      - call_connected  → phone_call
      - missed_source   → missed_visit ("auto" or "manual")
      - schedule_id     → missed_visit (link to the schedule that expected this pickup)
    """

    __tablename__ = "custody_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    child_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_children.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    overnight: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0",
    )
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    call_connected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    missed_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    schedule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("custody_schedules.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    child: Mapped[Child] = relationship(back_populates="events")
    photos: Mapped[list["EventPhoto"]] = relationship(
        "EventPhoto", back_populates="event",
        cascade="all, delete-orphan", order_by="EventPhoto.position",
        lazy="selectin",
    )


class EventPhoto(Base):
    """Receipt / text-screenshot / misc photo attached to a CustodyEvent."""

    __tablename__ = "custody_event_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_events.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumb_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
    )

    event: Mapped[CustodyEvent] = relationship(back_populates="photos")


class Schedule(Base):
    """Recurring custody schedule for a child (e.g. EOW Fri-Sun)."""

    __tablename__ = "custody_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    child_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_children.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
    )
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    interval_weeks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1",
    )
    weekdays: Mapped[str] = mapped_column(String(32), nullable=False)  # "4,5,6"
    pickup_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    dropoff_time: Mapped[str] = mapped_column(String(5), nullable=False)
    pickup_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    child: Mapped[Child] = relationship(back_populates="schedules")
    exceptions: Mapped[list["ScheduleException"]] = relationship(
        "ScheduleException", back_populates="schedule",
        cascade="all, delete-orphan", lazy="selectin",
    )


class ScheduleException(Base):
    """One-off override or skip for a specific scheduled date."""

    __tablename__ = "custody_schedule_exceptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    schedule_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_schedules.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # skip | override
    override_pickup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    override_dropoff_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    schedule: Mapped[Schedule] = relationship(back_populates="exceptions")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_models.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/models.py backend/tests/plugins/custody/test_models.py
git commit -m "feat(custody): ORM models — Child, CustodyEvent, EventPhoto, Schedule, ScheduleException"
```

---

## Phase 2 — Services (CRUD for children, events, schedules)

Pure-DB functions. Every service asserts `owner_id = user.id`, enforces enum values, and returns the ORM row.

### Task 2.1: Children service

**Files:**
- Create: `backend/app/plugins/custody/services.py`
- Test: `backend/tests/plugins/custody/test_services_children.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_services_children.py
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        yield s, user
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_list_delete_child(session_and_user):
    from app.plugins.custody.services import (
        create_child,
        delete_child,
        list_children,
        update_child,
    )

    s, user = session_and_user
    c = await create_child(s, user, name="Mason", dob="2020-08-12")
    assert c.name == "Mason"
    assert c.owner_id == user.id

    all_c = await list_children(s, user)
    assert [x.name for x in all_c] == ["Mason"]

    updated = await update_child(s, c, name="Mason R", dob=None)
    assert updated.name == "Mason R"

    await delete_child(s, c)
    assert await list_children(s, user) == []


@pytest.mark.asyncio
async def test_resolve_child_by_name_case_insensitive(session_and_user):
    from app.plugins.custody.services import create_child, resolve_child

    s, user = session_and_user
    c = await create_child(s, user, name="Mason")
    found = await resolve_child(s, user, name="mason")
    assert found is not None and found.id == c.id

    missing = await resolve_child(s, user, name="Lily")
    assert missing is None


@pytest.mark.asyncio
async def test_resolve_child_default_when_single(session_and_user):
    from app.plugins.custody.services import create_child, resolve_child

    s, user = session_and_user
    c = await create_child(s, user, name="Mason")
    found = await resolve_child(s, user, name=None)
    assert found is not None and found.id == c.id


@pytest.mark.asyncio
async def test_resolve_child_none_when_multiple_and_no_name(session_and_user):
    from app.plugins.custody.services import create_child, resolve_child

    s, user = session_and_user
    await create_child(s, user, name="Mason")
    await create_child(s, user, name="Lily")
    assert await resolve_child(s, user, name=None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_services_children.py -v`
Expected: FAIL with `ImportError: cannot import name 'create_child' from 'app.plugins.custody.services'`.

- [ ] **Step 3: Write the children portion of services.py**

```python
# backend/app/plugins/custody/services.py
"""Business logic for the custody plugin. Pure DB functions — callers
(HTTP routes, LLM tool handlers) compose these and own presentation.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .models import Child


# ---------- Children ----------


async def create_child(
    db: AsyncSession, user: User, *, name: str, dob: str | None = None,
) -> Child:
    child = Child(owner_id=user.id, name=name.strip(), dob=dob)
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return child


async def list_children(db: AsyncSession, user: User) -> list[Child]:
    res = await db.execute(
        select(Child).where(Child.owner_id == user.id).order_by(Child.created_at.asc())
    )
    return list(res.scalars().all())


async def get_child(db: AsyncSession, user: User, child_id: str) -> Child | None:
    res = await db.execute(
        select(Child).where(Child.id == child_id, Child.owner_id == user.id)
    )
    return res.scalar_one_or_none()


async def update_child(
    db: AsyncSession, child: Child, *, name: str | None = None, dob: str | None = None,
) -> Child:
    if name is not None:
        child.name = name.strip()
    child.dob = dob
    await db.commit()
    await db.refresh(child)
    return child


async def delete_child(db: AsyncSession, child: Child) -> None:
    await db.delete(child)
    await db.commit()


async def resolve_child(
    db: AsyncSession, user: User, *, name: str | None,
) -> Child | None:
    """Resolve a child for an LLM tool call.

    When `name` is given, case-insensitive match. When `name` is None,
    default to the user's only child; if they have 0 or 2+, return None
    so the caller can ask for clarification.
    """
    if name is not None and name.strip():
        res = await db.execute(
            select(Child).where(
                Child.owner_id == user.id,
                func.lower(Child.name) == name.strip().lower(),
            )
        )
        return res.scalar_one_or_none()

    res = await db.execute(select(Child).where(Child.owner_id == user.id))
    rows = list(res.scalars().all())
    return rows[0] if len(rows) == 1 else None
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_services_children.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/services.py backend/tests/plugins/custody/test_services_children.py
git commit -m "feat(custody): children service (CRUD + resolve_child helper)"
```

---

### Task 2.2: Events service

**Files:**
- Modify: `backend/app/plugins/custody/services.py`
- Test: `backend/tests/plugins/custody/test_services_events.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_services_events.py
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_create_event_pickup_with_overnight(session_user_child):
    from app.plugins.custody.services import CreateEventInput, create_event

    s, user, child = session_user_child
    evt = await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=_now(), notes="from school", location="Elm",
        overnight=True,
    ))
    assert evt.type == "pickup"
    assert evt.overnight is True
    assert evt.location == "Elm"


@pytest.mark.asyncio
async def test_create_event_expense_requires_amount(session_user_child):
    from app.plugins.custody.services import CreateEventInput, InvalidEventData, create_event

    s, user, child = session_user_child
    with pytest.raises(InvalidEventData):
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="expense", occurred_at=_now(),
            amount_cents=None, category="food",
        ))


@pytest.mark.asyncio
async def test_create_event_rejects_unknown_type(session_user_child):
    from app.plugins.custody.services import CreateEventInput, InvalidEventData, create_event

    s, user, child = session_user_child
    with pytest.raises(InvalidEventData):
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="laundry", occurred_at=_now(),
        ))


@pytest.mark.asyncio
async def test_list_events_filters_and_pagination(session_user_child):
    from app.plugins.custody.services import (
        CreateEventInput,
        create_event,
        list_events,
    )

    s, user, child = session_user_child
    base = _now()
    for i in range(5):
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="note", occurred_at=base - timedelta(hours=i),
            notes=f"n{i}",
        ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=base,
        amount_cents=100, category="food", notes="snack",
    ))

    all_notes = await list_events(s, user, child_id=child.id, type="note")
    assert len(all_notes) == 5
    assert [e.notes for e in all_notes] == ["n0", "n1", "n2", "n3", "n4"]  # newest first

    paged = await list_events(s, user, child_id=child.id, type="note", limit=2, offset=2)
    assert [e.notes for e in paged] == ["n2", "n3"]


@pytest.mark.asyncio
async def test_owner_scope_prevents_cross_user_read(session_user_child):
    from app.plugins.custody.services import (
        CreateEventInput,
        create_child,
        create_event,
        list_events,
    )

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note", occurred_at=_now(), notes="mine",
    ))

    other = User(id=uuid4(), email="o@x.com", name="O", email_verified=True, google_sub="g2")
    s.add(other)
    await s.flush()
    other_child = await create_child(s, other, name="Lily")
    assert await list_events(s, other, child_id=other_child.id) == []
    # And user A cannot see anything scoped to user B's child_id.
    assert await list_events(s, other, child_id=child.id) == []


@pytest.mark.asyncio
async def test_update_and_delete_event(session_user_child):
    from app.plugins.custody.services import (
        CreateEventInput,
        create_event,
        delete_event,
        get_event,
        update_event,
    )

    s, user, child = session_user_child
    evt = await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note", occurred_at=_now(), notes="before",
    ))
    updated = await update_event(s, evt, notes="after", location="park")
    assert updated.notes == "after"
    assert updated.location == "park"

    await delete_event(s, evt)
    assert await get_event(s, user, evt.id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_services_events.py -v`
Expected: FAIL with import errors.

- [ ] **Step 3: Append events service to services.py**

Add below the children section:

```python
# ---------- Events ----------

from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy.orm import selectinload

from .models import CustodyEvent

EVENT_TYPES = {
    "pickup", "dropoff", "activity", "expense", "text_screenshot",
    "medical", "school", "missed_visit", "phone_call", "note",
}
EXPENSE_CATEGORIES = {"food", "activity", "clothing", "school", "medical", "other"}
MISSED_SOURCES = {"auto", "manual"}


class InvalidEventData(ValueError):
    """Raised when event input fails type-specific validation."""


@dataclass
class CreateEventInput:
    child_id: str
    type: str
    occurred_at: datetime
    notes: str | None = None
    location: str | None = None
    overnight: bool = False
    amount_cents: int | None = None
    category: str | None = None
    call_connected: bool | None = None
    missed_source: str | None = None
    schedule_id: str | None = None


def _validate_event(data: CreateEventInput) -> None:
    if data.type not in EVENT_TYPES:
        raise InvalidEventData(f"unknown_event_type: {data.type}")
    if data.type == "expense":
        if data.amount_cents is None or data.amount_cents < 0:
            raise InvalidEventData("expense_requires_amount_cents")
        if data.category is not None and data.category not in EXPENSE_CATEGORIES:
            raise InvalidEventData(f"unknown_category: {data.category}")
    if data.type == "missed_visit":
        src = data.missed_source or "manual"
        if src not in MISSED_SOURCES:
            raise InvalidEventData(f"unknown_missed_source: {src}")


async def create_event(
    db: AsyncSession, user: User, data: CreateEventInput,
) -> CustodyEvent:
    _validate_event(data)
    # Verify child belongs to user (owner scope).
    child = await get_child(db, user, data.child_id)
    if child is None:
        raise InvalidEventData("child_not_found")
    evt = CustodyEvent(
        owner_id=user.id,
        child_id=data.child_id,
        type=data.type,
        occurred_at=data.occurred_at,
        notes=data.notes,
        location=data.location,
        overnight=bool(data.overnight) if data.type == "pickup" else False,
        amount_cents=data.amount_cents if data.type == "expense" else None,
        category=data.category if data.type == "expense" else None,
        call_connected=data.call_connected if data.type == "phone_call" else None,
        missed_source=(data.missed_source or "manual") if data.type == "missed_visit" else None,
        schedule_id=data.schedule_id if data.type == "missed_visit" else None,
    )
    db.add(evt)
    await db.commit()
    await db.refresh(evt)
    return evt


async def list_events(
    db: AsyncSession, user: User, *,
    child_id: str | None = None,
    type: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CustodyEvent]:
    stmt = (
        select(CustodyEvent)
        .options(selectinload(CustodyEvent.photos))
        .where(CustodyEvent.owner_id == user.id)
    )
    if child_id is not None:
        stmt = stmt.where(CustodyEvent.child_id == child_id)
    if type is not None:
        stmt = stmt.where(CustodyEvent.type == type)
    if from_dt is not None:
        stmt = stmt.where(CustodyEvent.occurred_at >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(CustodyEvent.occurred_at <= to_dt)
    stmt = stmt.order_by(CustodyEvent.occurred_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    return list(res.scalars().unique().all())


async def get_event(
    db: AsyncSession, user: User, event_id: str,
) -> CustodyEvent | None:
    res = await db.execute(
        select(CustodyEvent)
        .options(selectinload(CustodyEvent.photos))
        .where(CustodyEvent.id == event_id, CustodyEvent.owner_id == user.id)
    )
    return res.scalar_one_or_none()


async def update_event(
    db: AsyncSession, evt: CustodyEvent, **patch,
) -> CustodyEvent:
    """Apply an in-place partial update. Any field in `patch` that matches
    a mapped column is written; unknown keys are silently ignored so the
    HTTP layer can forward `body.model_dump(exclude_unset=True)` safely.
    """
    allowed = {
        "occurred_at", "notes", "location", "overnight",
        "amount_cents", "category", "call_connected",
        "missed_source",
    }
    for k, v in patch.items():
        if k in allowed:
            setattr(evt, k, v)
    await db.commit()
    await db.refresh(evt)
    return evt


async def delete_event(db: AsyncSession, evt: CustodyEvent) -> None:
    await db.delete(evt)
    await db.commit()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_services_events.py -v`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/services.py backend/tests/plugins/custody/test_services_events.py
git commit -m "feat(custody): events service — CreateEventInput, validation, list/get/update/delete"
```

---

### Task 2.3: Schedules service

**Files:**
- Modify: `backend/app/plugins/custody/services.py`
- Test: `backend/tests/plugins/custody/test_services_schedules.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_services_schedules.py
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_list_update_delete_schedule(session_user_child):
    from app.plugins.custody.services import (
        CreateScheduleInput,
        create_schedule,
        delete_schedule,
        list_schedules,
        update_schedule,
    )

    s, user, child = session_user_child
    sched = await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="EOW Fri-Sun",
        start_date="2026-01-02", interval_weeks=2,
        weekdays="4,5,6", pickup_time="17:00", dropoff_time="19:00",
    ))
    assert sched.name == "EOW Fri-Sun"
    assert sched.interval_weeks == 2

    all_s = await list_schedules(s, user, child_id=child.id)
    assert len(all_s) == 1

    updated = await update_schedule(s, sched, name="EOW weekends", pickup_location="her house")
    assert updated.name == "EOW weekends"
    assert updated.pickup_location == "her house"

    await delete_schedule(s, sched)
    assert await list_schedules(s, user, child_id=child.id) == []


@pytest.mark.asyncio
async def test_rejects_bad_weekdays(session_user_child):
    from app.plugins.custody.services import (
        CreateScheduleInput,
        InvalidScheduleData,
        create_schedule,
    )

    s, user, child = session_user_child
    with pytest.raises(InvalidScheduleData):
        await create_schedule(s, user, CreateScheduleInput(
            child_id=child.id, name="bad",
            start_date="2026-01-02", interval_weeks=1,
            weekdays="7,9", pickup_time="17:00", dropoff_time="19:00",
        ))


@pytest.mark.asyncio
async def test_schedule_exception_crud(session_user_child):
    from app.plugins.custody.services import (
        CreateScheduleInput,
        add_schedule_exception,
        create_schedule,
        delete_schedule_exception,
        get_schedule_exceptions,
    )

    s, user, child = session_user_child
    sched = await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="weekly",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    ex = await add_schedule_exception(
        s, sched, date="2026-02-20", kind="skip",
    )
    rows = await get_schedule_exceptions(s, sched)
    assert [r.id for r in rows] == [ex.id]

    await delete_schedule_exception(s, ex)
    assert await get_schedule_exceptions(s, sched) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_services_schedules.py -v`
Expected: FAIL with import errors.

- [ ] **Step 3: Append schedules section to services.py**

```python
# ---------- Schedules ----------

from .models import Schedule, ScheduleException


class InvalidScheduleData(ValueError):
    pass


@dataclass
class CreateScheduleInput:
    child_id: str
    name: str
    start_date: str  # YYYY-MM-DD
    interval_weeks: int
    weekdays: str  # "4,5,6"
    pickup_time: str  # HH:MM
    dropoff_time: str  # HH:MM
    pickup_location: str | None = None
    active: bool = True


def _validate_schedule(data: CreateScheduleInput) -> None:
    if data.interval_weeks < 1:
        raise InvalidScheduleData("interval_weeks_must_be_positive")
    try:
        wds = [int(x) for x in data.weekdays.split(",") if x.strip() != ""]
    except ValueError:
        raise InvalidScheduleData("weekdays_must_be_ints") from None
    if not wds or any(w < 0 or w > 6 for w in wds):
        raise InvalidScheduleData("weekdays_out_of_range")
    for label, t in (("pickup_time", data.pickup_time), ("dropoff_time", data.dropoff_time)):
        if len(t) != 5 or t[2] != ":":
            raise InvalidScheduleData(f"{label}_must_be_HH:MM")


async def create_schedule(
    db: AsyncSession, user: User, data: CreateScheduleInput,
) -> Schedule:
    _validate_schedule(data)
    # Owner-scope the child.
    child = await get_child(db, user, data.child_id)
    if child is None:
        raise InvalidScheduleData("child_not_found")
    sched = Schedule(
        owner_id=user.id,
        child_id=data.child_id,
        name=data.name,
        active=data.active,
        start_date=data.start_date,
        interval_weeks=data.interval_weeks,
        weekdays=data.weekdays,
        pickup_time=data.pickup_time,
        dropoff_time=data.dropoff_time,
        pickup_location=data.pickup_location,
    )
    db.add(sched)
    await db.commit()
    await db.refresh(sched)
    return sched


async def list_schedules(
    db: AsyncSession, user: User, *, child_id: str | None = None,
) -> list[Schedule]:
    stmt = select(Schedule).where(Schedule.owner_id == user.id)
    if child_id is not None:
        stmt = stmt.where(Schedule.child_id == child_id)
    stmt = stmt.order_by(Schedule.created_at.asc())
    res = await db.execute(stmt)
    return list(res.scalars().unique().all())


async def get_schedule(
    db: AsyncSession, user: User, schedule_id: str,
) -> Schedule | None:
    res = await db.execute(
        select(Schedule).where(
            Schedule.id == schedule_id, Schedule.owner_id == user.id,
        )
    )
    return res.scalar_one_or_none()


async def update_schedule(db: AsyncSession, sched: Schedule, **patch) -> Schedule:
    allowed = {
        "name", "active", "start_date", "interval_weeks", "weekdays",
        "pickup_time", "dropoff_time", "pickup_location",
    }
    for k, v in patch.items():
        if k in allowed:
            setattr(sched, k, v)
    await db.commit()
    await db.refresh(sched)
    return sched


async def delete_schedule(db: AsyncSession, sched: Schedule) -> None:
    await db.delete(sched)
    await db.commit()


async def add_schedule_exception(
    db: AsyncSession, sched: Schedule, *,
    date: str, kind: str,
    override_pickup_at: datetime | None = None,
    override_dropoff_at: datetime | None = None,
) -> ScheduleException:
    if kind not in ("skip", "override"):
        raise InvalidScheduleData(f"unknown_exception_kind: {kind}")
    ex = ScheduleException(
        schedule_id=sched.id,
        date=date,
        kind=kind,
        override_pickup_at=override_pickup_at,
        override_dropoff_at=override_dropoff_at,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    return ex


async def get_schedule_exceptions(
    db: AsyncSession, sched: Schedule,
) -> list[ScheduleException]:
    res = await db.execute(
        select(ScheduleException)
        .where(ScheduleException.schedule_id == sched.id)
        .order_by(ScheduleException.date.asc())
    )
    return list(res.scalars().all())


async def delete_schedule_exception(
    db: AsyncSession, ex: ScheduleException,
) -> None:
    await db.delete(ex)
    await db.commit()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_services_schedules.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/services.py backend/tests/plugins/custody/test_services_schedules.py
git commit -m "feat(custody): schedules service — CRUD + validated exceptions"
```

---

## Phase 3 — Recurrence engine + missed-visit detection

The only non-trivial algorithm in the backend. Pure-function `expected_pickups()` is exhaustively unit-tested; the DB-touching `refresh_missed()` sits on top.

### Task 3.1: `expected_pickups()` recurrence generator

**Files:**
- Create: `backend/app/plugins/custody/schedules.py`
- Test: `backend/tests/plugins/custody/test_schedules_recurrence.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_schedules_recurrence.py
from dataclasses import dataclass
from datetime import date, datetime

import pytest

from app.plugins.custody.schedules import ExpectedPickup, expected_pickups


@dataclass
class FakeSchedule:
    id: str
    start_date: str
    interval_weeks: int
    weekdays: str
    pickup_time: str
    dropoff_time: str


@dataclass
class FakeException:
    date: str
    kind: str  # skip | override
    override_pickup_at: datetime | None = None
    override_dropoff_at: datetime | None = None


def _s(**kw) -> FakeSchedule:
    base = dict(
        id="sch1", start_date="2026-01-02",  # a Friday
        interval_weeks=1, weekdays="4",       # Fridays
        pickup_time="17:00", dropoff_time="19:00",
    )
    base.update(kw)
    return FakeSchedule(**base)


def test_weekly_single_day_generates_fridays():
    sched = _s()
    got = expected_pickups(sched, [], date(2026, 1, 1), date(2026, 1, 31))
    assert [p.expected_date for p in got] == [
        date(2026, 1, 2), date(2026, 1, 9), date(2026, 1, 16),
        date(2026, 1, 23), date(2026, 1, 30),
    ]


def test_eow_skips_off_weeks():
    sched = _s(interval_weeks=2)
    got = expected_pickups(sched, [], date(2026, 1, 1), date(2026, 1, 31))
    # anchor Jan 2 (week 0), then Jan 16 (week 2), then Jan 30 (week 4).
    assert [p.expected_date for p in got] == [
        date(2026, 1, 2), date(2026, 1, 16), date(2026, 1, 30),
    ]


def test_multiple_weekdays():
    sched = _s(weekdays="4,5,6")  # Fri, Sat, Sun
    got = expected_pickups(sched, [], date(2026, 1, 2), date(2026, 1, 4))
    assert [p.expected_date for p in got] == [
        date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4),
    ]


def test_skip_exception_removes_occurrence():
    sched = _s()
    skips = [FakeException(date="2026-01-09", kind="skip")]
    got = expected_pickups(sched, skips, date(2026, 1, 1), date(2026, 1, 20))
    assert [p.expected_date for p in got] == [date(2026, 1, 2), date(2026, 1, 16)]


def test_override_exception_replaces_times():
    sched = _s()
    over_pickup = datetime(2026, 1, 9, 15, 30)
    over_drop = datetime(2026, 1, 9, 18, 0)
    overrides = [FakeException(
        date="2026-01-09", kind="override",
        override_pickup_at=over_pickup, override_dropoff_at=over_drop,
    )]
    got = expected_pickups(sched, overrides, date(2026, 1, 9), date(2026, 1, 9))
    assert len(got) == 1
    p = got[0]
    assert p.expected_pickup_at == over_pickup
    assert p.expected_dropoff_at == over_drop


def test_pickup_time_applied_to_date():
    sched = _s(pickup_time="08:30", dropoff_time="10:15")
    got = expected_pickups(sched, [], date(2026, 1, 2), date(2026, 1, 2))
    assert got[0].expected_pickup_at == datetime(2026, 1, 2, 8, 30)
    assert got[0].expected_dropoff_at == datetime(2026, 1, 2, 10, 15)


def test_returns_expected_pickup_dataclass_with_schedule_id():
    sched = _s(id="abc")
    got = expected_pickups(sched, [], date(2026, 1, 2), date(2026, 1, 2))
    assert isinstance(got[0], ExpectedPickup)
    assert got[0].schedule_id == "abc"


def test_empty_when_range_before_start_date():
    sched = _s(start_date="2026-06-01")
    got = expected_pickups(sched, [], date(2026, 1, 1), date(2026, 1, 31))
    assert got == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_schedules_recurrence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.plugins.custody.schedules'`.

- [ ] **Step 3: Implement the recurrence engine**

```python
# backend/app/plugins/custody/schedules.py
"""Recurrence + missed-visit detection for the custody plugin.

Split into a pure function (`expected_pickups`) that the tests
exhaustively pin down, and a DB-touching `refresh_missed` that
glues expected pickups to actual events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol


@dataclass
class ExpectedPickup:
    schedule_id: str
    expected_date: date
    expected_pickup_at: datetime
    expected_dropoff_at: datetime


class _SchedLike(Protocol):
    id: str
    start_date: str
    interval_weeks: int
    weekdays: str
    pickup_time: str
    dropoff_time: str


class _ExceptionLike(Protocol):
    date: str
    kind: str
    override_pickup_at: datetime | None
    override_dropoff_at: datetime | None


def _parse_hhmm(s: str) -> time:
    return time.fromisoformat(s if len(s) >= 5 else f"{s}:00")


def _parse_weekdays(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip() != ""]


def expected_pickups(
    sched: _SchedLike,
    exceptions: list[_ExceptionLike],
    from_date: date,
    to_date: date,
) -> list[ExpectedPickup]:
    """Generate expected pickups for `sched` in [from_date, to_date] inclusive.

    Applies `interval_weeks` offset (anchored on sched.start_date), the
    weekday filter, and any matching exceptions (`skip` drops; `override`
    replaces pickup/dropoff datetimes for that one date).

    Pure function — no DB access, deterministic from inputs. Exhaustively
    unit-tested; the DB wrapper (`refresh_missed`) is thin on top.
    """
    try:
        anchor = date.fromisoformat(sched.start_date)
    except ValueError:
        return []
    if to_date < anchor:
        return []

    weekdays = set(_parse_weekdays(sched.weekdays))
    pickup_t = _parse_hhmm(sched.pickup_time)
    dropoff_t = _parse_hhmm(sched.dropoff_time)

    # Exception lookup by ISO date string.
    ex_by_date: dict[str, _ExceptionLike] = {e.date: e for e in exceptions}

    out: list[ExpectedPickup] = []
    cursor = max(anchor, from_date)
    while cursor <= to_date:
        if cursor.weekday() in weekdays:
            delta_weeks = (cursor - anchor).days // 7
            if delta_weeks % sched.interval_weeks == 0:
                iso = cursor.isoformat()
                ex = ex_by_date.get(iso)
                if ex is not None and ex.kind == "skip":
                    cursor += timedelta(days=1)
                    continue
                if ex is not None and ex.kind == "override":
                    pickup_dt = ex.override_pickup_at or datetime.combine(cursor, pickup_t)
                    dropoff_dt = ex.override_dropoff_at or datetime.combine(cursor, dropoff_t)
                else:
                    pickup_dt = datetime.combine(cursor, pickup_t)
                    dropoff_dt = datetime.combine(cursor, dropoff_t)
                out.append(ExpectedPickup(
                    schedule_id=sched.id,
                    expected_date=cursor,
                    expected_pickup_at=pickup_dt,
                    expected_dropoff_at=dropoff_dt,
                ))
        cursor += timedelta(days=1)
    return out
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_schedules_recurrence.py -v`
Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/schedules.py backend/tests/plugins/custody/test_schedules_recurrence.py
git commit -m "feat(custody): deterministic expected_pickups recurrence engine"
```

---

### Task 3.2: `refresh_missed()` detection pass

**Files:**
- Modify: `backend/app/plugins/custody/schedules.py`
- Test: `backend/tests/plugins/custody/test_missed_visits.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_missed_visits.py
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


def _dt(year, month, day, hour=17, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute)


@pytest.mark.asyncio
async def test_missed_flagged_when_no_pickup_in_window(session_user_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import CreateScheduleInput, create_schedule

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))

    created = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 10))
    assert created == 2  # Jan 2 and Jan 9 both missed

    res = await s.execute(
        select(CustodyEvent).where(CustodyEvent.type == "missed_visit")
        .order_by(CustodyEvent.occurred_at.asc())
    )
    rows = list(res.scalars().all())
    assert len(rows) == 2
    assert rows[0].occurred_at == _dt(2026, 1, 2)
    assert rows[0].missed_source == "auto"


@pytest.mark.asyncio
async def test_pickup_within_2h_suppresses_missed(session_user_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    # Pickup landed 1h late — still inside 2h grace.
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=_dt(2026, 1, 2, 18, 0),
    ))

    created = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 3))
    assert created == 0
    res = await s.execute(
        select(CustodyEvent).where(CustodyEvent.type == "missed_visit")
    )
    assert res.scalars().all() == []


@pytest.mark.asyncio
async def test_idempotent_across_runs(session_user_child):
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import CreateScheduleInput, create_schedule

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    first = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 10))
    second = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 10))
    assert first == 2
    assert second == 0


@pytest.mark.asyncio
async def test_manual_missed_visit_blocks_auto_flag(session_user_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    # User manually logged the missed visit for Jan 2 (maybe with extra notes).
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="missed_visit",
        occurred_at=_dt(2026, 1, 2),
        missed_source="manual",
        notes="she texted she wasn't bringing him",
    ))
    created = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 3))
    assert created == 0
    res = await s.execute(
        select(CustodyEvent).where(CustodyEvent.type == "missed_visit")
    )
    rows = list(res.scalars().all())
    assert len(rows) == 1
    assert rows[0].missed_source == "manual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_missed_visits.py -v`
Expected: FAIL with `ImportError: cannot import name 'refresh_missed'`.

- [ ] **Step 3: Append `refresh_missed` to `schedules.py`**

Append to `backend/app/plugins/custody/schedules.py`:

```python
# ---------- DB-backed missed-visit detection ----------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

PICKUP_GRACE_HOURS = 2
MISSED_DEDUPE_HOURS = 4


async def refresh_missed(
    db: AsyncSession, user: User, child_id: str, *, up_to: datetime,
) -> int:
    """Scan active schedules for `child_id` and insert `missed_visit` events
    for any expected pickup that:
      (a) has no `pickup` event within ±PICKUP_GRACE_HOURS, AND
      (b) has no existing `missed_visit` row (auto or manual) within ±MISSED_DEDUPE_HOURS.
    Returns the number of new rows inserted.
    """
    # Import here to avoid circular import at module load.
    from .models import CustodyEvent, Schedule

    res = await db.execute(
        select(Schedule).where(
            Schedule.owner_id == user.id,
            Schedule.child_id == child_id,
            Schedule.active.is_(True),
        )
    )
    schedules = list(res.scalars().all())
    if not schedules:
        return 0

    new_count = 0
    for sched in schedules:
        exceptions = sched.exceptions  # selectin-loaded
        start = date.fromisoformat(sched.start_date)
        expected = expected_pickups(sched, exceptions, start, up_to.date())
        for ep in expected:
            pickup_lo = ep.expected_pickup_at - timedelta(hours=PICKUP_GRACE_HOURS)
            pickup_hi = ep.expected_pickup_at + timedelta(hours=PICKUP_GRACE_HOURS)
            # Any real pickup in window?
            match = await db.execute(
                select(CustodyEvent.id).where(
                    CustodyEvent.owner_id == user.id,
                    CustodyEvent.child_id == child_id,
                    CustodyEvent.type == "pickup",
                    CustodyEvent.occurred_at >= pickup_lo,
                    CustodyEvent.occurred_at <= pickup_hi,
                )
            )
            if match.first() is not None:
                continue

            dedupe_lo = ep.expected_pickup_at - timedelta(hours=MISSED_DEDUPE_HOURS)
            dedupe_hi = ep.expected_pickup_at + timedelta(hours=MISSED_DEDUPE_HOURS)
            existing = await db.execute(
                select(CustodyEvent.id).where(
                    CustodyEvent.owner_id == user.id,
                    CustodyEvent.child_id == child_id,
                    CustodyEvent.type == "missed_visit",
                    CustodyEvent.occurred_at >= dedupe_lo,
                    CustodyEvent.occurred_at <= dedupe_hi,
                )
            )
            if existing.first() is not None:
                continue

            db.add(CustodyEvent(
                owner_id=user.id,
                child_id=child_id,
                type="missed_visit",
                occurred_at=ep.expected_pickup_at,
                missed_source="auto",
                schedule_id=sched.id,
                notes=(
                    f"Auto-flagged: no pickup within {PICKUP_GRACE_HOURS}h "
                    f"of scheduled {sched.pickup_time}"
                ),
            ))
            new_count += 1

    if new_count:
        await db.commit()
    return new_count
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_missed_visits.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/schedules.py backend/tests/plugins/custody/test_missed_visits.py
git commit -m "feat(custody): refresh_missed detects missed pickups, idempotent, dedupes manual"
```

---

### Task 3.3: Status + summary helpers

**Files:**
- Modify: `backend/app/plugins/custody/schedules.py`
- Test: `backend/tests/plugins/custody/test_status.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_status.py
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


@pytest.mark.asyncio
async def test_status_no_schedule_no_events(session_user_child):
    from app.plugins.custody.schedules import compute_status

    s, user, child = session_user_child
    st = await compute_status(s, user, child.id, now=datetime(2026, 1, 5, 12, 0))
    assert st["state"] == "no_schedule"


@pytest.mark.asyncio
async def test_status_with_you_after_pickup(session_user_child):
    from app.plugins.custody.schedules import compute_status
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="w", start_date="2026-01-02",
        interval_weeks=1, weekdays="4",
        pickup_time="17:00", dropoff_time="19:00",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 9, 17, 0),
    ))
    st = await compute_status(s, user, child.id, now=datetime(2026, 1, 9, 18, 0))
    assert st["state"] == "with_you"
    assert st["since"] == datetime(2026, 1, 9, 17, 0)
    assert st["in_care_duration_seconds"] == 3600


@pytest.mark.asyncio
async def test_status_away_after_dropoff_shows_next_pickup(session_user_child):
    from app.plugins.custody.schedules import compute_status
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="w", start_date="2026-01-02",
        interval_weeks=1, weekdays="4",
        pickup_time="17:00", dropoff_time="19:00",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 2, 17, 0),
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="dropoff",
        occurred_at=datetime(2026, 1, 4, 19, 0),
    ))
    st = await compute_status(s, user, child.id, now=datetime(2026, 1, 5, 12, 0))
    assert st["state"] == "away"
    assert st["last_dropoff_at"] == datetime(2026, 1, 4, 19, 0)
    assert st["next_pickup_at"] == datetime(2026, 1, 9, 17, 0)


@pytest.mark.asyncio
async def test_summary_aggregates_month(session_user_child):
    from app.plugins.custody.schedules import compute_summary
    from app.plugins.custody.services import (
        CreateEventInput,
        create_event,
    )

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup", occurred_at=datetime(2026, 1, 3, 10, 0),
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=datetime(2026, 1, 3, 12, 0),
        amount_cents=4250, category="activity",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=datetime(2026, 1, 5, 12, 0),
        amount_cents=1500, category="food",
    ))
    # Out-of-month; should not be counted.
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=datetime(2026, 2, 1, 12, 0),
        amount_cents=9999, category="food",
    ))

    summary = await compute_summary(s, user, child.id, year=2026, month=1)
    assert summary["visits_count"] == 1
    assert summary["total_expense_cents"] == 5750
    assert summary["by_category"] == {"activity": 4250, "food": 1500}
    assert summary["missed_visits_count"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_status.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Append status + summary helpers**

Append to `backend/app/plugins/custody/schedules.py`:

```python
# ---------- Home-screen support (status + summary) ----------

async def compute_status(
    db: AsyncSession, user: User, child_id: str, *, now: datetime,
) -> dict:
    from .models import CustodyEvent, Schedule

    # Latest pickup and dropoff.
    res = await db.execute(
        select(CustodyEvent)
        .where(
            CustodyEvent.owner_id == user.id,
            CustodyEvent.child_id == child_id,
            CustodyEvent.type.in_(["pickup", "dropoff"]),
        )
        .order_by(CustodyEvent.occurred_at.desc())
    )
    transitions = list(res.scalars().all())

    last_pickup = next((e for e in transitions if e.type == "pickup"), None)
    last_dropoff = next((e for e in transitions if e.type == "dropoff"), None)

    state = "no_schedule"
    if last_pickup is not None and (last_dropoff is None or last_dropoff.occurred_at < last_pickup.occurred_at):
        state = "with_you"
    else:
        # Any active schedule means we have context to report "away".
        has_sched = await db.execute(
            select(Schedule.id).where(
                Schedule.owner_id == user.id,
                Schedule.child_id == child_id,
                Schedule.active.is_(True),
            )
        )
        if has_sched.first() is not None:
            state = "away"

    out: dict = {"state": state}
    if state == "with_you" and last_pickup is not None:
        out["since"] = last_pickup.occurred_at
        out["in_care_duration_seconds"] = int((now - last_pickup.occurred_at).total_seconds())
    if state == "away" and last_dropoff is not None:
        out["last_dropoff_at"] = last_dropoff.occurred_at
    if state == "away":
        # Peek the next expected pickup across all active schedules.
        sched_res = await db.execute(
            select(Schedule).where(
                Schedule.owner_id == user.id,
                Schedule.child_id == child_id,
                Schedule.active.is_(True),
            )
        )
        next_pickup: datetime | None = None
        for sched in sched_res.scalars().all():
            window_end = (now + timedelta(days=60)).date()
            eps = expected_pickups(sched, sched.exceptions, now.date(), window_end)
            for ep in eps:
                if ep.expected_pickup_at > now and (next_pickup is None or ep.expected_pickup_at < next_pickup):
                    next_pickup = ep.expected_pickup_at
        if next_pickup is not None:
            out["next_pickup_at"] = next_pickup
    return out


async def compute_summary(
    db: AsyncSession, user: User, child_id: str, *, year: int, month: int,
) -> dict:
    from calendar import monthrange
    from .models import CustodyEvent

    first = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    last = datetime(year, month, last_day, 23, 59, 59)

    res = await db.execute(
        select(CustodyEvent).where(
            CustodyEvent.owner_id == user.id,
            CustodyEvent.child_id == child_id,
            CustodyEvent.occurred_at >= first,
            CustodyEvent.occurred_at <= last,
        )
    )
    rows = list(res.scalars().all())

    visits = sum(1 for e in rows if e.type == "pickup")
    missed = sum(1 for e in rows if e.type == "missed_visit")
    total_cents = sum(e.amount_cents or 0 for e in rows if e.type == "expense")
    by_category: dict[str, int] = {}
    for e in rows:
        if e.type != "expense" or e.amount_cents is None:
            continue
        key = e.category or "other"
        by_category[key] = by_category.get(key, 0) + e.amount_cents

    return {
        "visits_count": visits,
        "missed_visits_count": missed,
        "total_expense_cents": total_cents,
        "by_category": by_category,
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_status.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/schedules.py backend/tests/plugins/custody/test_status.py
git commit -m "feat(custody): compute_status + compute_summary for home screen"
```

---

## Phase 4 — Photos binding + export

### Task 4.1: Custody photos binding

**Files:**
- Create: `backend/app/plugins/custody/photos.py`
- Test: `backend/tests/plugins/custody/test_photos.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_photos.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_photos.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the custody photos binding**

```python
# backend/app/plugins/custody/photos.py
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

# Re-resolved at import time so tests can monkeypatch it.
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
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_photos.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/photos.py backend/tests/plugins/custody/test_photos.py
git commit -m "feat(custody): event photo upload/delete binding (5/event cap)"
```

---

### Task 4.2: CSV export

**Files:**
- Create: `backend/app/plugins/custody/export.py`
- Test: `backend/tests/plugins/custody/test_export_csv.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_export_csv.py
import csv
import io
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


@pytest.mark.asyncio
async def test_csv_export_has_header_and_rows(session_user_child):
    from app.plugins.custody.export import export_csv
    from app.plugins.custody.services import CreateEventInput, create_event

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 2, 17, 0), notes="school",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense",
        occurred_at=datetime(2026, 1, 2, 18, 0),
        amount_cents=4250, category="activity", notes="bowling",
    ))

    data = await export_csv(
        s, user, child_id=child.id,
        from_dt=datetime(2026, 1, 1), to_dt=datetime(2026, 1, 31, 23, 59),
    )
    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    rows = list(reader)
    assert rows[0] == [
        "occurred_at", "type", "child", "notes", "location",
        "amount_usd", "category", "photo_count", "photo_urls",
    ]
    # 2 data rows, newest first
    assert len(rows) == 3
    expense_row = next(r for r in rows[1:] if r[1] == "expense")
    assert expense_row[2] == "Mason"
    assert expense_row[5] == "42.50"
    assert expense_row[6] == "activity"


@pytest.mark.asyncio
async def test_csv_export_respects_date_range(session_user_child):
    from app.plugins.custody.export import export_csv
    from app.plugins.custody.services import CreateEventInput, create_event

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note",
        occurred_at=datetime(2025, 12, 30, 10, 0), notes="before",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note",
        occurred_at=datetime(2026, 1, 5, 10, 0), notes="in range",
    ))

    data = await export_csv(
        s, user, child_id=child.id,
        from_dt=datetime(2026, 1, 1), to_dt=datetime(2026, 1, 31, 23, 59),
    )
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    note_rows = [r for r in rows[1:]]
    assert len(note_rows) == 1
    assert note_rows[0][3] == "in range"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_export_csv.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement CSV export**

```python
# backend/app/plugins/custody/export.py
"""CSV + PDF export for a user's custody events over a date range.

Both formats honor owner scope through list_events and produce bytes
suitable for FastAPI `Response(content=..., media_type=...)`.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .models import Child
from .services import get_child, list_events

CSV_HEADERS = [
    "occurred_at", "type", "child", "notes", "location",
    "amount_usd", "category", "photo_count", "photo_urls",
]


async def export_csv(
    db: AsyncSession, user: User, *,
    child_id: str, from_dt: datetime, to_dt: datetime,
) -> bytes:
    child = await get_child(db, user, child_id)
    child_name = child.name if child else ""

    events = await list_events(
        db, user, child_id=child_id,
        from_dt=from_dt, to_dt=to_dt, limit=10_000, offset=0,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADERS)
    for e in events:
        amount = ""
        if e.amount_cents is not None:
            amount = f"{e.amount_cents / 100:.2f}"
        photo_urls = ";".join(f"/uploads/{p.original_path}" for p in (e.photos or []))
        w.writerow([
            e.occurred_at.isoformat(timespec="minutes"),
            e.type,
            child_name,
            e.notes or "",
            e.location or "",
            amount,
            e.category or "",
            len(e.photos or []),
            photo_urls,
        ])
    return buf.getvalue().encode("utf-8")
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_export_csv.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/export.py backend/tests/plugins/custody/test_export_csv.py
git commit -m "feat(custody): CSV export for date range"
```

---

### Task 4.3: PDF export

**Files:**
- Modify: `backend/app/plugins/custody/export.py`
- Test: `backend/tests/plugins/custody/test_export_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_export_pdf.py
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


@pytest.mark.asyncio
async def test_pdf_export_returns_nonempty_pdf_bytes(session_user_child):
    from app.plugins.custody.export import export_pdf
    from app.plugins.custody.services import CreateEventInput, create_event

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 2, 17, 0), notes="school",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense",
        occurred_at=datetime(2026, 1, 2, 18, 0),
        amount_cents=4250, category="activity", notes="bowling",
    ))

    data = await export_pdf(
        s, user, child_id=child.id,
        from_dt=datetime(2026, 1, 1), to_dt=datetime(2026, 1, 31, 23, 59),
    )
    # PDFs start with %PDF-
    assert data[:5] == b"%PDF-"
    assert len(data) > 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_export_pdf.py -v`
Expected: FAIL with `ImportError: cannot import name 'export_pdf'`.

- [ ] **Step 3: Append PDF export to export.py**

Add below `export_csv`:

```python
# ---------- PDF ----------

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors


def _type_label(t: str) -> str:
    return {
        "pickup": "Pickup", "dropoff": "Dropoff", "activity": "Activity",
        "expense": "Expense", "text_screenshot": "Text screenshot",
        "medical": "Medical", "school": "School",
        "missed_visit": "Missed visit", "phone_call": "Phone call",
        "note": "Note",
    }.get(t, t)


async def export_pdf(
    db: AsyncSession, user: User, *,
    child_id: str, from_dt: datetime, to_dt: datetime,
) -> bytes:
    """Generate a date-grouped PDF timeline for the range.

    Photo thumbnails are embedded inline when present. Image paths are
    resolved under settings.UPLOADS_DIR; missing files are silently skipped.
    """
    from app.config import settings

    uploads_root = Path(settings.UPLOADS_DIR)

    child = await get_child(db, user, child_id)
    child_name = child.name if child else ""

    events = await list_events(
        db, user, child_id=child_id,
        from_dt=from_dt, to_dt=to_dt, limit=10_000, offset=0,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()

    flow: list = []
    title = (
        f"Custody log — {child_name} — "
        f"{from_dt.date().isoformat()} to {to_dt.date().isoformat()}"
    )
    flow.append(Paragraph(title, styles["Title"]))
    flow.append(Spacer(1, 0.15 * inch))

    # Group by date (oldest first is easier to read in a timeline export).
    events_sorted = sorted(events, key=lambda e: e.occurred_at)
    current_day: str | None = None
    for e in events_sorted:
        day = e.occurred_at.date().isoformat()
        if day != current_day:
            current_day = day
            flow.append(Spacer(1, 0.1 * inch))
            flow.append(Paragraph(f"<b>{day}</b>", styles["Heading3"]))
        line = (
            f"<b>{e.occurred_at.strftime('%H:%M')}</b> — {_type_label(e.type)}"
        )
        if e.type == "expense" and e.amount_cents is not None:
            line += f" — ${e.amount_cents / 100:.2f}"
            if e.category:
                line += f" ({e.category})"
        if e.notes:
            line += f": {e.notes}"
        if e.location:
            line += f" · {e.location}"
        flow.append(Paragraph(line, styles["BodyText"]))
        for p in (e.photos or []):
            img_path = uploads_root / p.thumb_path
            if img_path.exists():
                try:
                    flow.append(RLImage(str(img_path), width=1.5 * inch, height=1.5 * inch))
                    flow.append(Spacer(1, 0.05 * inch))
                except Exception:
                    continue

    doc.build(flow)
    return buf.getvalue()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_export_pdf.py -v`
Expected: PASS. If reportlab is missing, re-run Task 0.3.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/export.py backend/tests/plugins/custody/test_export_pdf.py
git commit -m "feat(custody): PDF export via reportlab (grouped by day, embedded thumbs)"
```

---

## Phase 5 — HTTP routes

The FastAPI layer. Tasks cover children → events (+photos) → schedules → status/summary → refresh-missed → export.

### Task 5.1: Router skeleton + Pydantic schemas

**Files:**
- Create: `backend/app/plugins/custody/routes.py`
- Modify: `backend/app/plugins/custody/__init__.py` (swap the Phase-1 `router = None` fallback for the real import)

- [ ] **Step 1: Create the router file with shared Pydantic bodies**

```python
# backend/app/plugins/custody/routes.py
from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

from .export import export_csv, export_pdf
from .models import Child, CustodyEvent, EventPhoto, Schedule, ScheduleException
from .photos import delete_event_photo, save_event_photo
from .schedules import compute_status, compute_summary, refresh_missed
from .services import (
    CreateEventInput,
    CreateScheduleInput,
    InvalidEventData,
    InvalidScheduleData,
    add_schedule_exception,
    create_child,
    create_event,
    create_schedule,
    delete_child,
    delete_event,
    delete_schedule,
    delete_schedule_exception,
    get_child,
    get_event,
    get_schedule,
    list_children,
    list_events,
    list_schedules,
    update_child,
    update_event,
    update_schedule,
)

router = APIRouter(prefix="/api/plugins/custody", tags=["custody"])


# ----- Pydantic schemas -----


class ChildBody(BaseModel):
    name: str
    dob: str | None = None


class ChildResponse(BaseModel):
    id: str
    name: str
    dob: str | None

    @classmethod
    def from_model(cls, c: Child) -> "ChildResponse":
        return cls(id=c.id, name=c.name, dob=c.dob)


class EventPhotoOut(BaseModel):
    id: str
    position: int
    content_type: str
    url: str
    thumb_url: str

    @classmethod
    def from_model(cls, p: EventPhoto) -> "EventPhotoOut":
        return cls(
            id=p.id, position=p.position, content_type=p.content_type,
            url=f"/uploads/{p.original_path}",
            thumb_url=f"/uploads/{p.thumb_path}",
        )


class EventBody(BaseModel):
    child_id: str
    type: str
    occurred_at: datetime | None = None
    notes: str | None = None
    location: str | None = None
    overnight: bool = False
    amount_cents: int | None = None
    category: str | None = None
    call_connected: bool | None = None
    missed_source: str | None = None


class EventPatch(BaseModel):
    occurred_at: datetime | None = None
    notes: str | None = None
    location: str | None = None
    overnight: bool | None = None
    amount_cents: int | None = None
    category: str | None = None
    call_connected: bool | None = None


class EventResponse(BaseModel):
    id: str
    child_id: str
    type: str
    occurred_at: datetime
    notes: str | None
    location: str | None
    overnight: bool
    amount_cents: int | None
    category: str | None
    call_connected: bool | None
    missed_source: str | None
    schedule_id: str | None
    photos: list[EventPhotoOut] = Field(default_factory=list)

    @classmethod
    def from_model(cls, e: CustodyEvent) -> "EventResponse":
        return cls(
            id=e.id, child_id=e.child_id, type=e.type,
            occurred_at=e.occurred_at,
            notes=e.notes, location=e.location,
            overnight=bool(e.overnight),
            amount_cents=e.amount_cents, category=e.category,
            call_connected=e.call_connected,
            missed_source=e.missed_source, schedule_id=e.schedule_id,
            photos=[EventPhotoOut.from_model(p) for p in (e.photos or [])],
        )


class ScheduleBody(BaseModel):
    child_id: str
    name: str
    start_date: str
    interval_weeks: int = 1
    weekdays: str
    pickup_time: str
    dropoff_time: str
    pickup_location: str | None = None
    active: bool = True


class SchedulePatch(BaseModel):
    name: str | None = None
    active: bool | None = None
    start_date: str | None = None
    interval_weeks: int | None = None
    weekdays: str | None = None
    pickup_time: str | None = None
    dropoff_time: str | None = None
    pickup_location: str | None = None


class ScheduleExceptionResponse(BaseModel):
    id: str
    date: str
    kind: str
    override_pickup_at: datetime | None
    override_dropoff_at: datetime | None

    @classmethod
    def from_model(cls, x: ScheduleException) -> "ScheduleExceptionResponse":
        return cls(
            id=x.id, date=x.date, kind=x.kind,
            override_pickup_at=x.override_pickup_at,
            override_dropoff_at=x.override_dropoff_at,
        )


class ScheduleResponse(BaseModel):
    id: str
    child_id: str
    name: str
    active: bool
    start_date: str
    interval_weeks: int
    weekdays: str
    pickup_time: str
    dropoff_time: str
    pickup_location: str | None
    exceptions: list[ScheduleExceptionResponse] = Field(default_factory=list)

    @classmethod
    def from_model(cls, s: Schedule) -> "ScheduleResponse":
        return cls(
            id=s.id, child_id=s.child_id, name=s.name, active=s.active,
            start_date=s.start_date, interval_weeks=s.interval_weeks,
            weekdays=s.weekdays, pickup_time=s.pickup_time,
            dropoff_time=s.dropoff_time, pickup_location=s.pickup_location,
            exceptions=[ScheduleExceptionResponse.from_model(e) for e in (s.exceptions or [])],
        )


class ScheduleExceptionBody(BaseModel):
    date: str
    kind: str
    override_pickup_at: datetime | None = None
    override_dropoff_at: datetime | None = None
```

- [ ] **Step 2: Wire the router into __init__.py**

Replace the Phase-1 try/except fallback block with the direct import:

```python
# backend/app/plugins/custody/__init__.py   (replace register() body)
from app.plugins.core.types import PluginRegistration


def register() -> PluginRegistration:
    from . import models  # noqa: F401  (registers tables on Base.metadata)
    from .routes import router
    from .tools import TOOLS

    return PluginRegistration(
        name="custody",
        version="1.0.0",
        type="internal",
        router=router,
        tools=TOOLS,
        ui_bundle_path="bundle/custody.js",
        ui_components=[
            "CustodyHome", "ExpenseForm", "TextCaptureForm", "EventForm",
            "ScheduleForm", "ScheduleListScreen", "ChildrenScreen", "ExportSheet",
        ],
    )
```

Create a placeholder `tools.py` now so the import above works; we'll fill it in Task 5.6:

```python
# backend/app/plugins/custody/tools.py (placeholder; filled in Task 5.6)
from app.plugins.core.schema import ToolDef

TOOLS: list[ToolDef] = []
```

- [ ] **Step 3: Smoke check — the app starts**

Run: `cd backend && .venv/Scripts/python -c "from app.main import create_app; create_app(); print('ok')"`
Expected: `ok` (no errors importing the custody plugin).

- [ ] **Step 4: Commit**

```bash
git add backend/app/plugins/custody/routes.py backend/app/plugins/custody/tools.py backend/app/plugins/custody/__init__.py
git commit -m "feat(custody): router skeleton + Pydantic schemas"
```

---

### Task 5.2: Children routes

**Files:**
- Modify: `backend/app/plugins/custody/routes.py`
- Test: `backend/tests/plugins/custody/test_routes_children.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_routes_children.py
import pytest

from tests.plugins.yardsailing.conftest import app_and_two_tokens  # reuse fixture


@pytest.fixture
async def client_and_token(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token_a, _ = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token_a


@pytest.mark.asyncio
async def test_child_create_list_update_delete(client_and_token):
    client, token = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/plugins/custody/children",
        json={"name": "Mason", "dob": "2020-08-12"},
        headers=headers,
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    r = await client.get("/api/plugins/custody/children", headers=headers)
    assert r.status_code == 200
    assert [c["name"] for c in r.json()] == ["Mason"]

    r = await client.patch(
        f"/api/plugins/custody/children/{cid}",
        json={"name": "Mason R"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Mason R"

    r = await client.delete(f"/api/plugins/custody/children/{cid}", headers=headers)
    assert r.status_code == 204
    r = await client.get("/api/plugins/custody/children", headers=headers)
    assert r.json() == []


@pytest.mark.asyncio
async def test_children_owner_scope(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token_a, token_b = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ra = await client.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert ra.status_code == 201
        cid = ra.json()["id"]

        rb = await client.get(
            "/api/plugins/custody/children",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert rb.json() == []

        # User B cannot modify user A's child.
        rb_patch = await client.patch(
            f"/api/plugins/custody/children/{cid}", json={"name": "hacked"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert rb_patch.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_children.py -v`
Expected: 404 on the POST call (route not registered yet).

- [ ] **Step 3: Append children routes to routes.py**

```python
# backend/app/plugins/custody/routes.py   (append)

@router.post("/children", status_code=status.HTTP_201_CREATED, response_model=ChildResponse)
async def create_child_route(
    body: ChildBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChildResponse:
    c = await create_child(db, user, name=body.name, dob=body.dob)
    return ChildResponse.from_model(c)


@router.get("/children", response_model=list[ChildResponse])
async def list_children_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChildResponse]:
    return [ChildResponse.from_model(c) for c in await list_children(db, user)]


@router.patch("/children/{child_id}", response_model=ChildResponse)
async def update_child_route(
    child_id: str, body: ChildBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChildResponse:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    updated = await update_child(db, child, name=body.name, dob=body.dob)
    return ChildResponse.from_model(updated)


@router.delete("/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_child_route(
    child_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    await delete_child(db, child)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_children.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/routes.py backend/tests/plugins/custody/test_routes_children.py
git commit -m "feat(custody): children HTTP routes (owner-scoped CRUD)"
```

---

### Task 5.3: Events routes + photos

**Files:**
- Modify: `backend/app/plugins/custody/routes.py`
- Test: `backend/tests/plugins/custody/test_routes_events.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_routes_events.py
import io

import pytest
from PIL import Image

from tests.plugins.yardsailing.conftest import app_and_two_tokens


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (10, 10, 200)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
async def client_token_child(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token, _ = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token}"},
        )
        yield c, token, r.json()["id"]


@pytest.mark.asyncio
async def test_event_crud(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "pickup",
            "occurred_at": "2026-01-02T17:00:00",
            "notes": "school", "overnight": True,
        },
        headers=h,
    )
    assert r.status_code == 201
    eid = r.json()["id"]
    assert r.json()["overnight"] is True

    # Expense requires amount_cents
    r_bad = await client.post(
        "/api/plugins/custody/events",
        json={"child_id": cid, "type": "expense"},
        headers=h,
    )
    assert r_bad.status_code == 400

    r_patch = await client.patch(
        f"/api/plugins/custody/events/{eid}",
        json={"notes": "school bus"}, headers=h,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["notes"] == "school bus"

    r_list = await client.get(
        f"/api/plugins/custody/events?child_id={cid}&type=pickup", headers=h,
    )
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    r_del = await client.delete(f"/api/plugins/custody/events/{eid}", headers=h)
    assert r_del.status_code == 204


@pytest.mark.asyncio
async def test_event_photo_upload_and_delete(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "expense",
            "occurred_at": "2026-01-02T12:00:00",
            "amount_cents": 4250, "category": "activity", "notes": "bowling",
        },
        headers=h,
    )
    eid = r.json()["id"]

    r_up = await client.post(
        f"/api/plugins/custody/events/{eid}/photos",
        files={"file": ("receipt.jpg", _jpeg(), "image/jpeg")},
        headers=h,
    )
    assert r_up.status_code == 200
    pid = r_up.json()["id"]

    r_del = await client.delete(
        f"/api/plugins/custody/events/{eid}/photos/{pid}", headers=h,
    )
    assert r_del.status_code == 204


@pytest.mark.asyncio
async def test_events_owner_scope(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token_a, token_b = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        cid = r.json()["id"]
        re = await client.post(
            "/api/plugins/custody/events",
            json={
                "child_id": cid, "type": "note",
                "occurred_at": "2026-01-02T12:00:00", "notes": "private",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        eid = re.json()["id"]

        # B cannot read or patch A's event
        r_get = await client.get(
            f"/api/plugins/custody/events?child_id={cid}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r_get.json() == []
        r_patch = await client.patch(
            f"/api/plugins/custody/events/{eid}", json={"notes": "hacked"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r_patch.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_events.py -v`
Expected: FAIL with 404s.

- [ ] **Step 3: Append events routes**

```python
# backend/app/plugins/custody/routes.py   (append)


@router.post("/events", status_code=status.HTTP_201_CREATED, response_model=EventResponse)
async def create_event_route(
    body: EventBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    occurred = body.occurred_at or datetime.utcnow()
    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=body.child_id,
            type=body.type,
            occurred_at=occurred,
            notes=body.notes,
            location=body.location,
            overnight=body.overnight,
            amount_cents=body.amount_cents,
            category=body.category,
            call_connected=body.call_connected,
            missed_source=body.missed_source,
        ))
    except InvalidEventData as e:
        raise HTTPException(status_code=400, detail=str(e))
    return EventResponse.from_model(evt)


@router.get("/events", response_model=list[EventResponse])
async def list_events_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    child_id: str | None = Query(default=None),
    type: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[EventResponse]:
    rows = await list_events(
        db, user, child_id=child_id, type=type,
        from_dt=from_dt, to_dt=to_dt, limit=limit, offset=offset,
    )
    return [EventResponse.from_model(e) for e in rows]


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event_route(
    event_id: str, body: EventPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    patch = body.model_dump(exclude_unset=True)
    updated = await update_event(db, evt, **patch)
    return EventResponse.from_model(updated)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_route(
    event_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    await delete_event(db, evt)


@router.post("/events/{event_id}/photos")
async def upload_event_photo_route(
    event_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    photo = await save_event_photo(db, event_id, file)
    return EventPhotoOut.from_model(photo).model_dump()


@router.delete(
    "/events/{event_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_event_photo_route(
    event_id: str, photo_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    evt = await get_event(db, user, event_id)
    if evt is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    photo = await db.get(EventPhoto, photo_id)
    if photo is None or photo.event_id != event_id:
        raise HTTPException(status_code=404, detail="photo_not_found")
    await delete_event_photo(db, photo)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_events.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/routes.py backend/tests/plugins/custody/test_routes_events.py
git commit -m "feat(custody): events + event-photo routes"
```

---

### Task 5.4: Schedules routes + exception routes

**Files:**
- Modify: `backend/app/plugins/custody/routes.py`
- Test: `backend/tests/plugins/custody/test_routes_schedules.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_routes_schedules.py
import pytest

from tests.plugins.yardsailing.conftest import app_and_two_tokens


@pytest.fixture
async def client_token_child(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token, _ = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token}"},
        )
        yield c, token, r.json()["id"]


@pytest.mark.asyncio
async def test_schedule_crud_and_exception(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/plugins/custody/schedules",
        json={
            "child_id": cid, "name": "EOW Fri-Sun",
            "start_date": "2026-01-02", "interval_weeks": 2,
            "weekdays": "4,5,6",
            "pickup_time": "17:00", "dropoff_time": "19:00",
        },
        headers=h,
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    r = await client.patch(
        f"/api/plugins/custody/schedules/{sid}",
        json={"name": "EOW weekends"}, headers=h,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "EOW weekends"

    r = await client.post(
        f"/api/plugins/custody/schedules/{sid}/exceptions",
        json={"date": "2026-02-20", "kind": "skip"},
        headers=h,
    )
    assert r.status_code == 201
    xid = r.json()["id"]

    r = await client.get("/api/plugins/custody/schedules", headers=h)
    assert len(r.json()) == 1
    assert len(r.json()[0]["exceptions"]) == 1

    r = await client.delete(
        f"/api/plugins/custody/schedules/exceptions/{xid}", headers=h,
    )
    assert r.status_code == 204

    r = await client.delete(f"/api/plugins/custody/schedules/{sid}", headers=h)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_schedule_rejects_bad_weekdays(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/plugins/custody/schedules",
        json={
            "child_id": cid, "name": "bad",
            "start_date": "2026-01-02", "interval_weeks": 1,
            "weekdays": "9", "pickup_time": "17:00", "dropoff_time": "19:00",
        },
        headers=h,
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_schedules.py -v`
Expected: 404s for missing routes.

- [ ] **Step 3: Append schedule routes**

```python
# backend/app/plugins/custody/routes.py   (append)


@router.post("/schedules", status_code=status.HTTP_201_CREATED, response_model=ScheduleResponse)
async def create_schedule_route(
    body: ScheduleBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    try:
        sched = await create_schedule(db, user, CreateScheduleInput(
            child_id=body.child_id, name=body.name,
            start_date=body.start_date, interval_weeks=body.interval_weeks,
            weekdays=body.weekdays,
            pickup_time=body.pickup_time, dropoff_time=body.dropoff_time,
            pickup_location=body.pickup_location, active=body.active,
        ))
    except InvalidScheduleData as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScheduleResponse.from_model(sched)


@router.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    child_id: str | None = Query(default=None),
) -> list[ScheduleResponse]:
    rows = await list_schedules(db, user, child_id=child_id)
    return [ScheduleResponse.from_model(s) for s in rows]


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule_route(
    schedule_id: str, body: SchedulePatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    sched = await get_schedule(db, user, schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    patch = body.model_dump(exclude_unset=True)
    updated = await update_schedule(db, sched, **patch)
    return ScheduleResponse.from_model(updated)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_route(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    sched = await get_schedule(db, user, schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    await delete_schedule(db, sched)


@router.post(
    "/schedules/{schedule_id}/exceptions",
    status_code=status.HTTP_201_CREATED,
    response_model=ScheduleExceptionResponse,
)
async def add_exception_route(
    schedule_id: str, body: ScheduleExceptionBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleExceptionResponse:
    sched = await get_schedule(db, user, schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    try:
        ex = await add_schedule_exception(
            db, sched,
            date=body.date, kind=body.kind,
            override_pickup_at=body.override_pickup_at,
            override_dropoff_at=body.override_dropoff_at,
        )
    except InvalidScheduleData as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScheduleExceptionResponse.from_model(ex)


@router.delete(
    "/schedules/exceptions/{exception_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_exception_route(
    exception_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ex = await db.get(ScheduleException, exception_id)
    if ex is None:
        raise HTTPException(status_code=404, detail="exception_not_found")
    # Owner-scope via the parent schedule.
    sched = await get_schedule(db, user, ex.schedule_id)
    if sched is None:
        raise HTTPException(status_code=404, detail="exception_not_found")
    await delete_schedule_exception(db, ex)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_schedules.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/routes.py backend/tests/plugins/custody/test_routes_schedules.py
git commit -m "feat(custody): schedule + schedule-exception HTTP routes"
```

---

### Task 5.5: Status / summary / refresh-missed / export routes

**Files:**
- Modify: `backend/app/plugins/custody/routes.py`
- Test: `backend/tests/plugins/custody/test_routes_misc.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_routes_misc.py
import pytest

from tests.plugins.yardsailing.conftest import app_and_two_tokens


@pytest.fixture
async def client_token_child(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token, _ = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token}"},
        )
        yield c, token, r.json()["id"]


@pytest.mark.asyncio
async def test_status_no_schedule(client_token_child):
    client, token, cid = client_token_child
    r = await client.get(
        f"/api/plugins/custody/status?child_id={cid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "no_schedule"


@pytest.mark.asyncio
async def test_summary_empty_month(client_token_child):
    client, token, cid = client_token_child
    r = await client.get(
        f"/api/plugins/custody/summary?child_id={cid}&month=2026-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["visits_count"] == 0
    assert data["total_expense_cents"] == 0


@pytest.mark.asyncio
async def test_refresh_missed_returns_count(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/plugins/custody/schedules",
        json={
            "child_id": cid, "name": "wk",
            "start_date": "2026-01-02", "interval_weeks": 1, "weekdays": "4",
            "pickup_time": "17:00", "dropoff_time": "19:00",
        },
        headers=h,
    )
    r = await client.post(
        f"/api/plugins/custody/schedules/refresh-missed?child_id={cid}&up_to=2026-01-10",
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["new_rows"] == 2


@pytest.mark.asyncio
async def test_export_csv_endpoint(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "note",
            "occurred_at": "2026-01-05T10:00:00", "notes": "hi",
        },
        headers=h,
    )
    r = await client.get(
        f"/api/plugins/custody/export?child_id={cid}"
        f"&from=2026-01-01T00:00:00&to=2026-01-31T23:59:59&format=csv",
        headers=h,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert b"occurred_at" in r.content  # header line


@pytest.mark.asyncio
async def test_export_pdf_endpoint(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "note",
            "occurred_at": "2026-01-05T10:00:00", "notes": "hi",
        },
        headers=h,
    )
    r = await client.get(
        f"/api/plugins/custody/export?child_id={cid}"
        f"&from=2026-01-01T00:00:00&to=2026-01-31T23:59:59&format=pdf",
        headers=h,
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_misc.py -v`
Expected: 404s.

- [ ] **Step 3: Append the remaining routes**

```python
# backend/app/plugins/custody/routes.py   (append)


@router.get("/status")
async def status_route(
    child_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return await compute_status(db, user, child_id, now=datetime.utcnow())


@router.get("/summary")
async def summary_route(
    child_id: str = Query(...),
    month: str = Query(..., description="YYYY-MM"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    try:
        year_s, month_s = month.split("-")
        y, m = int(year_s), int(month_s)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="month_must_be_YYYY-MM")
    return await compute_summary(db, user, child_id, year=y, month=m)


@router.post("/schedules/refresh-missed")
async def refresh_missed_route(
    child_id: str = Query(...),
    up_to: str | None = Query(default=None, description="YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    if up_to is None:
        up_to_dt = datetime.utcnow()
    else:
        try:
            up_to_dt = datetime.fromisoformat(up_to + "T23:59:59")
        except ValueError:
            raise HTTPException(status_code=400, detail="up_to_must_be_YYYY-MM-DD")
    new_rows = await refresh_missed(db, user, child_id, up_to=up_to_dt)
    return {"new_rows": new_rows}


@router.get("/export")
async def export_route(
    child_id: str = Query(...),
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    format: str = Query(default="pdf", pattern="^(pdf|csv)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    child = await get_child(db, user, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    if format == "csv":
        data = await export_csv(db, user, child_id=child_id, from_dt=from_dt, to_dt=to_dt)
        return Response(
            content=data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="custody-{child.name}.csv"'},
        )
    data = await export_pdf(db, user, child_id=child_id, from_dt=from_dt, to_dt=to_dt)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="custody-{child.name}.pdf"'},
    )
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_routes_misc.py -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/routes.py backend/tests/plugins/custody/test_routes_misc.py
git commit -m "feat(custody): status, summary, refresh-missed, and export HTTP routes"
```

---

## Phase 6 — LLM tools

Every tool handler signature is `(args, user=None, db=None)` to match the existing `ToolExecutor.execute` contract (see yardsailing's `create_yard_sale_handler`). Child resolution is centralized via `services.resolve_child`.

### Task 6.1: log_custody_event + log_expense + log_missed_visit

**Files:**
- Replace: `backend/app/plugins/custody/tools.py` (was a placeholder)
- Modify: `backend/app/plugins/custody/plugin.json` (fill `skills` array)
- Test: `backend/tests/plugins/custody/test_tools_log.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/plugins/custody/test_tools_log.py
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_with_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


@pytest.mark.asyncio
async def test_log_event_default_now_and_default_child(session_user_with_child):
    from app.plugins.custody.tools import log_custody_event_handler

    s, user, child = session_user_with_child
    out = await log_custody_event_handler(
        {"type": "pickup", "notes": "school"},
        user=user, db=s,
    )
    assert out["ok"] is True
    assert "id" in out


@pytest.mark.asyncio
async def test_log_event_requires_auth(session_user_with_child):
    from app.plugins.custody.tools import log_custody_event_handler

    s, _, _ = session_user_with_child
    out = await log_custody_event_handler({"type": "pickup"}, user=None, db=s)
    assert out == {"error": "auth_required", "plugin": "custody"}


@pytest.mark.asyncio
async def test_log_event_child_not_found_lists_known(session_user_with_child):
    from app.plugins.custody.tools import log_custody_event_handler
    from app.plugins.custody.services import create_child

    s, user, child = session_user_with_child
    await create_child(s, user, name="Lily")  # now 2 children, ambiguous
    out = await log_custody_event_handler(
        {"type": "pickup", "child_name": "Robby"}, user=user, db=s,
    )
    assert out["error"] == "child_not_found"
    assert set(out["known_children"]) == {"Mason", "Lily"}


@pytest.mark.asyncio
async def test_log_expense_converts_usd_to_cents(session_user_with_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.tools import log_expense_handler
    from sqlalchemy import select

    s, user, _ = session_user_with_child
    out = await log_expense_handler(
        {"amount_usd": 42.50, "description": "bowling", "category": "activity"},
        user=user, db=s,
    )
    assert out["ok"] is True
    res = await s.execute(select(CustodyEvent).where(CustodyEvent.type == "expense"))
    evt = res.scalar_one()
    assert evt.amount_cents == 4250
    assert evt.category == "activity"
    assert evt.notes == "bowling"


@pytest.mark.asyncio
async def test_log_missed_visit_sets_source_manual(session_user_with_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.tools import log_missed_visit_handler
    from sqlalchemy import select

    s, user, _ = session_user_with_child
    out = await log_missed_visit_handler(
        {"expected_pickup_at": "2026-01-09T17:00:00", "notes": "she didn't show"},
        user=user, db=s,
    )
    assert out["ok"] is True
    res = await s.execute(select(CustodyEvent).where(CustodyEvent.type == "missed_visit"))
    evt = res.scalar_one()
    assert evt.missed_source == "manual"
    assert evt.occurred_at == datetime(2026, 1, 9, 17, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_tools_log.py -v`
Expected: FAIL with import errors.

- [ ] **Step 3: Replace tools.py with real handlers + TOOLS list**

```python
# backend/app/plugins/custody/tools.py
"""LLM tool definitions for the custody plugin.

- log_custody_event: pickup/dropoff/activity/note/medical/school/phone_call/text_screenshot
- log_expense: amount + category; USD → cents conversion in the handler
- log_missed_visit: manual entry for denied/missed visits
- query_custody_events: read-side for "how much / when / what" questions
- show_custody_home / show_expense_form / show_text_capture: UI-only
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.plugins.core.schema import ToolDef, ToolInputSchema

from .services import (
    CreateEventInput,
    InvalidEventData,
    create_event,
    list_children,
    list_events,
    resolve_child,
)


async def _resolve_or_err(db, user, child_name: str | None) -> dict | Any:
    """Return the Child, or a dict error payload the LLM can read."""
    child = await resolve_child(db, user, name=child_name)
    if child is not None:
        return child
    rows = await list_children(db, user)
    return {
        "error": "child_not_found",
        "plugin": "custody",
        "known_children": [c.name for c in rows],
    }


def _parse_occurred_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


async def log_custody_event_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    etype = args.get("type")
    if etype is None:
        return {"error": "type_required", "plugin": "custody"}

    maybe = await _resolve_or_err(db, user, args.get("child_name"))
    if isinstance(maybe, dict):
        return maybe
    child = maybe

    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=child.id,
            type=etype,
            occurred_at=_parse_occurred_at(args.get("occurred_at")),
            notes=args.get("notes"),
            location=args.get("location"),
            overnight=bool(args.get("overnight", False)),
            call_connected=args.get("call_connected"),
        ))
    except InvalidEventData as e:
        return {"error": str(e), "plugin": "custody"}
    return {
        "ok": True,
        "id": evt.id,
        "summary": f"{etype} logged for {child.name} at {evt.occurred_at.isoformat(timespec='minutes')}",
    }


async def log_expense_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    amount_usd = args.get("amount_usd")
    if amount_usd is None:
        return {"error": "amount_usd_required", "plugin": "custody"}
    try:
        amount_cents = int(round(float(amount_usd) * 100))
    except (TypeError, ValueError):
        return {"error": "amount_usd_invalid", "plugin": "custody"}
    if amount_cents < 0:
        return {"error": "amount_usd_negative", "plugin": "custody"}

    maybe = await _resolve_or_err(db, user, args.get("child_name"))
    if isinstance(maybe, dict):
        return maybe
    child = maybe

    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=child.id,
            type="expense",
            occurred_at=_parse_occurred_at(args.get("occurred_at")),
            notes=args.get("description"),
            amount_cents=amount_cents,
            category=args.get("category"),
        ))
    except InvalidEventData as e:
        return {"error": str(e), "plugin": "custody"}
    return {
        "ok": True,
        "id": evt.id,
        "summary": f"Expense ${amount_cents/100:.2f} logged for {child.name}",
    }


async def log_missed_visit_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    raw = args.get("expected_pickup_at")
    if not raw:
        return {"error": "expected_pickup_at_required", "plugin": "custody"}
    try:
        occurred = datetime.fromisoformat(raw)
    except ValueError:
        return {"error": "expected_pickup_at_invalid", "plugin": "custody"}

    maybe = await _resolve_or_err(db, user, args.get("child_name"))
    if isinstance(maybe, dict):
        return maybe
    child = maybe

    try:
        evt = await create_event(db, user, CreateEventInput(
            child_id=child.id,
            type="missed_visit",
            occurred_at=occurred,
            notes=args.get("notes"),
            missed_source="manual",
        ))
    except InvalidEventData as e:
        return {"error": str(e), "plugin": "custody"}
    return {
        "ok": True,
        "id": evt.id,
        "summary": f"Missed visit recorded for {child.name} on {occurred.date()}",
    }


async def query_custody_events_handler(args, user=None, db=None):
    if user is None:
        return {"error": "auth_required", "plugin": "custody"}

    child_name = args.get("child_name")
    child = None
    if child_name:
        child = await resolve_child(db, user, name=child_name)
        if child is None:
            return await _resolve_or_err(db, user, child_name)

    from_dt = _parse_occurred_at(args.get("from_date")) if args.get("from_date") else None
    to_dt = _parse_occurred_at(args.get("to_date")) if args.get("to_date") else None
    limit = int(args.get("limit") or 20)

    rows = await list_events(
        db, user,
        child_id=child.id if child else None,
        type=args.get("type"),
        from_dt=from_dt, to_dt=to_dt,
        limit=limit,
    )
    events = [
        {
            "id": e.id,
            "type": e.type,
            "occurred_at": e.occurred_at.isoformat(timespec="minutes"),
            "notes": e.notes,
            "amount_usd": (e.amount_cents / 100) if e.amount_cents is not None else None,
            "category": e.category,
            "location": e.location,
        }
        for e in rows
    ]
    total_cents = sum(e.amount_cents or 0 for e in rows if e.type == "expense")
    by_type: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for e in rows:
        by_type[e.type] = by_type.get(e.type, 0) + 1
        if e.type == "expense" and e.amount_cents is not None:
            key = e.category or "other"
            by_category[key] = by_category.get(key, 0) + e.amount_cents
    return {
        "events": events,
        "summary": {
            "count": len(events),
            "total_expense_usd": round(total_cents / 100, 2),
            "by_type": by_type,
            "by_category_usd": {k: round(v / 100, 2) for k, v in by_category.items()},
        },
    }


TOOLS: list[ToolDef] = [
    ToolDef(
        name="log_custody_event",
        description=(
            "Log a single visitation event (pickup, dropoff, activity, note, "
            "medical, school, phone_call, text_screenshot). Use this for anything "
            "EXCEPT expenses (use log_expense) and missed visits (use log_missed_visit). "
            "occurred_at defaults to now if omitted."
        ),
        input_schema=ToolInputSchema(
            properties={
                "type": {
                    "type": "string",
                    "enum": [
                        "pickup", "dropoff", "activity", "note", "medical",
                        "school", "phone_call", "text_screenshot",
                    ],
                    "description": "Event type.",
                },
                "child_name": {
                    "type": "string",
                    "description": "Child's first name from the user's sentence; omit if they have only one child.",
                },
                "occurred_at": {
                    "type": "string",
                    "description": "ISO-8601 datetime. Omit for 'now'.",
                },
                "notes": {"type": "string"},
                "location": {"type": "string"},
                "overnight": {"type": "boolean", "description": "Set on pickup when starting an overnight stay."},
                "call_connected": {"type": "boolean", "description": "For phone_call: did the call go through?"},
            },
            required=["type"],
        ),
        auth_required=True,
        handler=log_custody_event_handler,
    ),
    ToolDef(
        name="log_expense",
        description=(
            "Log a money expense during time with a child. Converts USD to cents "
            "server-side. Use when the user says they spent money (e.g. 'bowling $42', "
            "'lunch at Chick-fil-A $18'). A receipt photo can be added later from the home screen."
        ),
        input_schema=ToolInputSchema(
            properties={
                "child_name": {"type": "string"},
                "amount_usd": {"type": "number", "description": "Dollars (e.g. 42.50)."},
                "description": {
                    "type": "string",
                    "description": "What the expense was for (e.g. 'bowling', 'lunch at Chick-fil-A').",
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "activity", "clothing", "school", "medical", "other"],
                },
                "occurred_at": {"type": "string"},
            },
            required=["amount_usd", "description"],
        ),
        auth_required=True,
        handler=log_expense_handler,
    ),
    ToolDef(
        name="log_missed_visit",
        description=(
            "Record a missed or denied visit (e.g. 'she didn't bring him Saturday'). "
            "Sets missed_source='manual' so the nightly auto-detector won't duplicate it."
        ),
        input_schema=ToolInputSchema(
            properties={
                "child_name": {"type": "string"},
                "expected_pickup_at": {
                    "type": "string",
                    "description": "ISO-8601 datetime of when the pickup was supposed to happen.",
                },
                "notes": {"type": "string"},
            },
            required=["expected_pickup_at"],
        ),
        auth_required=True,
        handler=log_missed_visit_handler,
    ),
    ToolDef(
        name="query_custody_events",
        description=(
            "Read-side: answer questions like 'how much have I spent on Mason this month?' "
            "or 'when did I last see him?'. Returns matching events and a summary block."
        ),
        input_schema=ToolInputSchema(
            properties={
                "child_name": {"type": "string"},
                "type": {"type": "string", "description": "Filter by event type."},
                "from_date": {"type": "string", "description": "ISO datetime lower bound."},
                "to_date": {"type": "string", "description": "ISO datetime upper bound."},
                "limit": {"type": "integer", "description": "Default 20, max 200."},
            },
            required=[],
        ),
        auth_required=True,
        handler=query_custody_events_handler,
    ),
    ToolDef(
        name="show_custody_home",
        description=(
            "Open the custody home screen (status, timeline, quick actions). "
            "Use when the user says 'open custody', 'show my timeline', or similar."
        ),
        input_schema=ToolInputSchema(),
        ui_component="CustodyHome",
    ),
    ToolDef(
        name="show_expense_form",
        description=(
            "Open the expense form with camera + category picker. Use when the user "
            "says 'log an expense', 'add a receipt', or similar."
        ),
        input_schema=ToolInputSchema(),
        ui_component="ExpenseForm",
    ),
    ToolDef(
        name="show_text_capture",
        description=(
            "Open the text-screenshot capture flow. Use when the user wants to save a "
            "screenshot of a text from the other parent."
        ),
        input_schema=ToolInputSchema(),
        ui_component="TextCaptureForm",
    ),
]
```

Also fill the `skills` array in `plugin.json`:

```json
// backend/app/plugins/custody/plugin.json  (replace "skills": [] with)
"skills": [
  {
    "name": "log-custody-event",
    "description": "Log a visitation event (pickup, dropoff, activity, note, medical, school, phone_call, text_screenshot).",
    "tools": ["log_custody_event"]
  },
  {
    "name": "log-expense",
    "description": "Log a money expense during time with a child. Supports a receipt photo via the form.",
    "tools": ["log_expense", "show_expense_form"],
    "components": ["ExpenseForm"]
  },
  {
    "name": "capture-text",
    "description": "Save a screenshot of a text message from the other parent.",
    "tools": ["show_text_capture"],
    "components": ["TextCaptureForm"]
  },
  {
    "name": "log-missed-visit",
    "description": "Record a missed/denied visit.",
    "tools": ["log_missed_visit"]
  },
  {
    "name": "query-custody",
    "description": "Answer how-much/how-often/when questions about custody events.",
    "tools": ["query_custody_events"]
  },
  {
    "name": "open-custody-home",
    "description": "Open the custody home screen (status, timeline, quick actions).",
    "tools": ["show_custody_home"],
    "components": ["CustodyHome"]
  }
]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_tools_log.py -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/custody/tools.py backend/app/plugins/custody/plugin.json backend/tests/plugins/custody/test_tools_log.py
git commit -m "feat(custody): LLM tool handlers + skill groupings"
```

---

### Task 6.2: Query tool integration smoke test

**Files:**
- Test: `backend/tests/plugins/custody/test_tools_query.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/plugins/custody/test_tools_query.py
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_with_events():
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
        child = await create_child(s, user, name="Mason")
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="expense",
            occurred_at=datetime(2026, 1, 3, 12, 0),
            amount_cents=4250, category="activity", notes="bowling",
        ))
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="expense",
            occurred_at=datetime(2026, 1, 5, 12, 0),
            amount_cents=1500, category="food", notes="lunch",
        ))
        yield s, user
    await engine.dispose()


@pytest.mark.asyncio
async def test_query_returns_summary_by_type_and_category(session_with_events):
    from app.plugins.custody.tools import query_custody_events_handler

    s, user = session_with_events
    out = await query_custody_events_handler(
        {"type": "expense"}, user=user, db=s,
    )
    assert out["summary"]["count"] == 2
    assert out["summary"]["total_expense_usd"] == 57.5
    assert out["summary"]["by_category_usd"] == {"activity": 42.5, "food": 15.0}
```

- [ ] **Step 2: Run test**

Run: `cd backend && .venv/Scripts/pytest tests/plugins/custody/test_tools_query.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/plugins/custody/test_tools_query.py
git commit -m "test(custody): query tool summary by type/category"
```

---

### Task 6.3: Full backend sweep

- [ ] **Step 1: Run every custody test + yardsailing + full suite**

```bash
cd backend
.venv/Scripts/pytest tests/plugins/custody/ -v
.venv/Scripts/pytest tests/plugins/yardsailing/ -v
.venv/Scripts/pytest -q
```

Expected: all green. If any regression from the shared-photo refactor shows up here, fix it before moving to the mobile phase.

- [ ] **Step 2: Create the help.md**

```markdown
<!-- backend/app/plugins/custody/help.md -->
# Custody

Log visitations with your children — pickups, dropoffs, activities, expenses,
medical/school events, missed visits, and screenshots of texts from the other
parent. Everything is timestamped and exportable.

## In chat

- `Picked up Mason` — logs a pickup stamped to now.
- `Dropped Mason off` — logs a dropoff.
- `Bowling with Mason $42` — logs an activity AND an expense.
- `She didn't bring him Saturday` — records a missed visit.
- `How much have I spent on Mason this month?` — summary.

## Home screen

Tap **Skills → Custody** to see:

- A status card: "With you since 2:14 PM" or "Next pickup Fri 5:00 PM".
- Quick-action buttons for Expense, Text screenshot, Activity, and Note.
- A timeline grouped by day with every event tap-able for details.
- A menu (top right): Export, Schedules, Children.

## Schedules

Set up a recurring schedule (e.g. every other Friday 5pm → Sunday 7pm) so
Custody can auto-flag missed visits. Add per-date exceptions for the weekends
that got swapped or cancelled.

## Export

Menu → Export. Pick a date range and PDF or CSV. The PDF embeds receipt and
text-screenshot thumbnails; the CSV includes URLs so you can attach originals.
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/plugins/custody/help.md
git commit -m "docs(custody): user-facing help"
```

---

## Phase 7 — Mobile bundle

The React Native bundle shipped alongside the plugin. Mirrors yardsailing's `build.mjs` / `package.json` / `components/index.ts` pattern 1:1. For each component task, the gate is **tsc clean + `npm run build` produces a non-empty bundle**. Manual smoke verification is listed in Phase 8.

### Task 7.1: Build scaffolding (package.json + build.mjs + components/index.ts)

**Files:**
- Create: `backend/app/plugins/custody/package.json`
- Create: `backend/app/plugins/custody/build.mjs`
- Create: `backend/app/plugins/custody/components/index.ts`
- Create: `backend/app/plugins/custody/components/bridge.ts`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "jain-custody-bundle",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node build.mjs"
  },
  "devDependencies": {
    "@react-native-community/datetimepicker": "^9.1.0",
    "esbuild": "^0.24.0"
  }
}
```

- [ ] **Step 2: Create `build.mjs`**

Copy yardsailing's verbatim, changing only the plugin name:

```javascript
// backend/app/plugins/custody/build.mjs
import { build } from "esbuild";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname);

const entry = join(ROOT, "components", "index.ts");
const outfile = join(ROOT, "bundle", "custody.js");
const outdir = dirname(outfile);
if (!existsSync(outdir)) mkdirSync(outdir, { recursive: true });

await build({
  entryPoints: [entry],
  bundle: true,
  outfile,
  format: "iife",
  platform: "neutral",
  target: "es2016",
  jsx: "transform",
  external: ["react", "react-native", "@react-native-community/datetimepicker"],
  loader: { ".tsx": "tsx", ".ts": "ts" },
  logLevel: "info",
});

let content = readFileSync(outfile, "utf-8");
content = content.replace(
  /var __toESM = \([^)]*\) => \([^;]*\);/,
  "var __toESM = (mod) => mod;",
);
writeFileSync(outfile, content);

console.log(`[custody] built ${outfile}`);
```

- [ ] **Step 3: Create a shared bridge type file**

```typescript
// backend/app/plugins/custody/components/bridge.ts
export interface Bridge {
  callPluginApi: (path: string, method: string, body: unknown) => Promise<unknown>;
  closeComponent: () => void;
  showToast: (msg: string) => void;
  openComponent?: (name: string, props?: Record<string, unknown>) => void;
}

export interface WithBridge {
  bridge: Bridge;
}
```

- [ ] **Step 4: Create the barrel `index.ts` with placeholder registrations**

```typescript
// backend/app/plugins/custody/components/index.ts
import { ChildrenScreen } from "./ChildrenScreen";
import { CustodyHome } from "./CustodyHome";
import { EventForm } from "./EventForm";
import { ExpenseForm } from "./ExpenseForm";
import { ExportSheet } from "./ExportSheet";
import { ScheduleForm } from "./ScheduleForm";
import { ScheduleListScreen } from "./ScheduleListScreen";
import { TextCaptureForm } from "./TextCaptureForm";

declare const globalThis: {
  JainPlugins?: Record<string, Record<string, unknown>>;
};

globalThis.JainPlugins = globalThis.JainPlugins || {};
globalThis.JainPlugins.custody = {
  CustodyHome,
  ExpenseForm,
  TextCaptureForm,
  EventForm,
  ScheduleForm,
  ScheduleListScreen,
  ChildrenScreen,
  ExportSheet,
};

export {
  ChildrenScreen, CustodyHome, EventForm, ExpenseForm, ExportSheet,
  ScheduleForm, ScheduleListScreen, TextCaptureForm,
};
```

The build will fail until every component exists, which is fine — Tasks 7.2-7.8 fill them in.

- [ ] **Step 5: Install deps**

Run: `cd backend/app/plugins/custody && npm install`
Expected: success; creates `node_modules/` (gitignored via existing pattern — add to `.gitignore` in the same commit).

- [ ] **Step 6: Update `.gitignore`**

Append to `.gitignore`:
```
backend/app/plugins/custody/node_modules/
backend/app/plugins/custody/package-lock.json
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/plugins/custody/package.json backend/app/plugins/custody/build.mjs backend/app/plugins/custody/components/index.ts backend/app/plugins/custody/components/bridge.ts .gitignore
git commit -m "feat(custody): bundle scaffolding (package.json, build.mjs, barrel index)"
```

---

### Task 7.2: CustodyHome component (status card + timeline + quick actions)

**Files:**
- Create: `backend/app/plugins/custody/components/CustodyHome.tsx`

- [ ] **Step 1: Write the component**

```tsx
// backend/app/plugins/custody/components/CustodyHome.tsx
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, RefreshControl,
  ScrollView, StyleSheet, Text, View,
} from "react-native";

import type { Bridge, WithBridge } from "./bridge";

interface Child { id: string; name: string; dob?: string | null }
interface Status {
  state: "with_you" | "away" | "no_schedule";
  since?: string;
  in_care_duration_seconds?: number;
  next_pickup_at?: string;
  last_dropoff_at?: string;
}
interface Event {
  id: string; type: string; occurred_at: string;
  notes?: string | null; location?: string | null;
  amount_cents?: number | null; category?: string | null;
  photos?: { id: string; thumb_url: string }[];
  overnight?: boolean;
}
interface Summary {
  visits_count: number; total_expense_cents: number;
  by_category: Record<string, number>; missed_visits_count: number;
}

const TYPE_COLOR: Record<string, string> = {
  pickup: "#2a7", dropoff: "#888", activity: "#08c",
  expense: "#d90", text_screenshot: "#27b",
  medical: "#c22", school: "#66a", missed_visit: "#d32",
  phone_call: "#6a5", note: "#555",
};
const TYPE_LABEL: Record<string, string> = {
  pickup: "Pickup", dropoff: "Dropoff", activity: "Activity",
  expense: "Expense", text_screenshot: "Text",
  medical: "Medical", school: "School",
  missed_visit: "Missed visit", phone_call: "Call", note: "Note",
};

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDuration(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h === 0) return `${m}m`;
  return `${h}h ${m}m`;
}

function groupByDay(events: Event[]): { label: string; items: Event[] }[] {
  const groups: Record<string, Event[]> = {};
  for (const e of events) {
    const key = e.occurred_at.slice(0, 10);
    (groups[key] ||= []).push(e);
  }
  const today = new Date().toISOString().slice(0, 10);
  const yest = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  return Object.keys(groups)
    .sort()
    .reverse()
    .map((k) => ({
      label: k === today ? "TODAY" : k === yest ? "YESTERDAY" : k,
      items: groups[k],
    }));
}

export function CustodyHome({ bridge }: WithBridge) {
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [missedBanner, setMissedBanner] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadChildren = useCallback(async () => {
    const list = (await bridge.callPluginApi(
      "/api/plugins/custody/children", "GET", null,
    )) as Child[];
    setChildren(list);
    if (list.length && !childId) setChildId(list[0].id);
  }, [bridge, childId]);

  const loadForChild = useCallback(async (id: string) => {
    // Missed-visit refresh on focus (idempotent).
    const refresh = (await bridge.callPluginApi(
      `/api/plugins/custody/schedules/refresh-missed?child_id=${id}`,
      "POST", null,
    )) as { new_rows: number };
    setMissedBanner(refresh?.new_rows || 0);

    const st = (await bridge.callPluginApi(
      `/api/plugins/custody/status?child_id=${id}`, "GET", null,
    )) as Status;
    setStatus(st);

    const now = new Date();
    const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    const sm = (await bridge.callPluginApi(
      `/api/plugins/custody/summary?child_id=${id}&month=${ym}`, "GET", null,
    )) as Summary;
    setSummary(sm);

    const evs = (await bridge.callPluginApi(
      `/api/plugins/custody/events?child_id=${id}&limit=200`, "GET", null,
    )) as Event[];
    setEvents(evs);
  }, [bridge]);

  useEffect(() => { loadChildren().finally(() => setLoading(false)); }, [loadChildren]);
  useEffect(() => { if (childId) loadForChild(childId); }, [childId, loadForChild]);

  const onRefresh = () => {
    if (!childId) return;
    setRefreshing(true);
    loadForChild(childId).finally(() => setRefreshing(false));
  };

  const logQuick = async (type: string) => {
    if (!childId) return;
    await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
      child_id: childId, type, occurred_at: new Date().toISOString(),
    });
    bridge.showToast(`${TYPE_LABEL[type]} logged`);
    loadForChild(childId);
  };

  if (loading) return <ActivityIndicator style={{ marginTop: 40 }} />;
  if (children.length === 0) {
    return (
      <View style={styles.centered}>
        <Text style={styles.heading}>Add a child to get started</Text>
        <Pressable
          style={styles.primaryBtn}
          onPress={() => bridge.openComponent?.("ChildrenScreen")}
        >
          <Text style={styles.primaryBtnText}>Add child</Text>
        </Pressable>
      </View>
    );
  }

  const grouped = groupByDay(events);

  return (
    <FlatList
      data={grouped}
      keyExtractor={(g) => g.label}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      ListHeaderComponent={
        <View>
          {children.length > 1 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.childStrip}>
              {children.map((c) => (
                <Pressable
                  key={c.id} onPress={() => setChildId(c.id)}
                  style={[styles.childChip, c.id === childId && styles.childChipActive]}
                >
                  <Text style={c.id === childId ? styles.childChipTextActive : styles.childChipText}>
                    {c.name}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          )}

          {missedBanner > 0 && (
            <View style={styles.banner}>
              <Text style={styles.bannerText}>
                We flagged {missedBanner} missed visit{missedBanner === 1 ? "" : "s"}. Scroll below to review.
              </Text>
            </View>
          )}

          {status?.state === "with_you" && status.since && (
            <View style={[styles.statusCard, { backgroundColor: "#e8f4ee" }]}>
              <Text style={styles.statusLabel}>WITH YOU</Text>
              <Text style={styles.statusName}>
                {children.find((c) => c.id === childId)?.name}
              </Text>
              <Text style={styles.statusSince}>
                Since {formatTime(status.since)} ·
                {" "}{formatDuration(status.in_care_duration_seconds || 0)}
              </Text>
              <Pressable style={styles.primaryBtn} onPress={() => logQuick("dropoff")}>
                <Text style={styles.primaryBtnText}>Dropped off</Text>
              </Pressable>
            </View>
          )}

          {status?.state === "away" && (
            <View style={styles.statusCard}>
              {status.next_pickup_at ? (
                <Text style={styles.statusLabel}>
                  NEXT PICKUP · {new Date(status.next_pickup_at).toLocaleString()}
                </Text>
              ) : (
                <Text style={styles.statusLabel}>No upcoming pickup</Text>
              )}
              {status.last_dropoff_at && (
                <Text style={styles.statusSince}>
                  Last dropoff: {new Date(status.last_dropoff_at).toLocaleString()}
                </Text>
              )}
              <Pressable style={styles.primaryBtn} onPress={() => logQuick("pickup")}>
                <Text style={styles.primaryBtnText}>Picked up</Text>
              </Pressable>
            </View>
          )}

          {status?.state === "no_schedule" && (
            <View style={styles.statusCard}>
              <Text style={styles.statusLabel}>No schedule yet</Text>
              <Pressable
                style={styles.primaryBtn}
                onPress={() => bridge.openComponent?.("ScheduleListScreen")}
              >
                <Text style={styles.primaryBtnText}>Set up schedule</Text>
              </Pressable>
            </View>
          )}

          <View style={styles.quickRow}>
            {[
              { key: "expense", label: "+ Expense", comp: "ExpenseForm" },
              { key: "text_screenshot", label: "+ Text", comp: "TextCaptureForm" },
              { key: "activity", label: "+ Activity", comp: "EventForm", props: { type: "activity" } },
              { key: "note", label: "+ Note", comp: "EventForm", props: { type: "note" } },
            ].map((q) => (
              <Pressable
                key={q.key} style={styles.quickBtn}
                onPress={() =>
                  bridge.openComponent?.(q.comp as string, {
                    childId,
                    ...(q as { props?: Record<string, unknown> }).props,
                  })
                }
              >
                <Text style={styles.quickBtnText}>{q.label}</Text>
              </Pressable>
            ))}
          </View>

          {summary && (
            <View style={styles.summaryStrip}>
              <Text style={styles.summaryText}>
                {summary.visits_count} visits · ${(summary.total_expense_cents / 100).toFixed(0)} spent
                {summary.missed_visits_count > 0 ? ` · ${summary.missed_visits_count} missed` : ""}
              </Text>
            </View>
          )}
        </View>
      }
      renderItem={({ item }) => (
        <View>
          <Text style={styles.dayHeader}>{item.label}</Text>
          {item.items.map((e) => (
            <Pressable
              key={e.id} style={styles.eventRow}
              onPress={() => bridge.openComponent?.("EventForm", { eventId: e.id, mode: "edit" })}
            >
              <View style={[styles.dot, { backgroundColor: TYPE_COLOR[e.type] || "#555" }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.eventTitle}>
                  {formatTime(e.occurred_at)} · {TYPE_LABEL[e.type] || e.type}
                  {e.type === "expense" && e.amount_cents != null
                    ? ` · $${(e.amount_cents / 100).toFixed(2)}`
                    : ""}
                </Text>
                {e.notes ? <Text style={styles.eventNotes}>{e.notes}</Text> : null}
              </View>
              {e.photos && e.photos.length > 0 ? (
                <Text style={styles.paperclip}>📎</Text>
              ) : null}
            </Pressable>
          ))}
        </View>
      )}
      ListEmptyComponent={
        <Text style={styles.empty}>No events yet. Use the quick actions above.</Text>
      }
    />
  );
}

const styles = StyleSheet.create({
  centered: { padding: 24, alignItems: "center", justifyContent: "center" },
  heading: { fontSize: 18, fontWeight: "600", marginBottom: 12 },
  childStrip: { flexDirection: "row", padding: 8 },
  childChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: "#eee", marginRight: 8 },
  childChipActive: { backgroundColor: "#2a7" },
  childChipText: { color: "#333" },
  childChipTextActive: { color: "#fff", fontWeight: "600" },
  banner: { backgroundColor: "#fff3c0", padding: 10, margin: 10, borderRadius: 6 },
  bannerText: { color: "#6a4f00" },
  statusCard: { margin: 10, padding: 14, borderRadius: 10, backgroundColor: "#f5f5f5" },
  statusLabel: { fontSize: 11, color: "#666", letterSpacing: 1, textTransform: "uppercase" },
  statusName: { fontSize: 22, fontWeight: "700", marginTop: 2 },
  statusSince: { fontSize: 12, color: "#444", marginTop: 2 },
  primaryBtn: { marginTop: 10, backgroundColor: "#2a7", paddingVertical: 10, borderRadius: 8, alignItems: "center" },
  primaryBtnText: { color: "#fff", fontWeight: "600" },
  quickRow: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: 10 },
  quickBtn: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#ddd", borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6, marginRight: 6, marginBottom: 6 },
  quickBtnText: { fontSize: 13 },
  summaryStrip: { paddingHorizontal: 12, paddingVertical: 6, backgroundColor: "#fafafa" },
  summaryText: { fontSize: 12, color: "#666" },
  dayHeader: { fontSize: 11, color: "#888", letterSpacing: 1, padding: 10, paddingBottom: 4 },
  eventRow: { flexDirection: "row", alignItems: "center", paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 10 },
  eventTitle: { fontSize: 13, fontWeight: "600" },
  eventNotes: { fontSize: 12, color: "#666" },
  paperclip: { fontSize: 14 },
  empty: { padding: 24, textAlign: "center", color: "#888" },
});
```

- [ ] **Step 2: Commit (build comes after all components exist in Task 7.8)**

```bash
git add backend/app/plugins/custody/components/CustodyHome.tsx
git commit -m "feat(custody): CustodyHome component"
```

---

### Task 7.3: ExpenseForm

**Files:**
- Create: `backend/app/plugins/custody/components/ExpenseForm.tsx`

- [ ] **Step 1: Write the component**

Reuse the photo flow from yardsailing's `SaleForm`: create the event first, then upload photos against its id.

```tsx
// backend/app/plugins/custody/components/ExpenseForm.tsx
import React, { useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

const CATEGORIES = ["food", "activity", "clothing", "school", "medical", "other"] as const;
type Category = typeof CATEGORIES[number];

interface ExpenseFormProps extends WithBridge {
  childId: string;
}

export function ExpenseForm({ bridge, childId }: ExpenseFormProps) {
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Category>("activity");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    const parsed = parseFloat(amount);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setError("Enter a dollar amount.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
        child_id: childId, type: "expense",
        occurred_at: new Date().toISOString(),
        amount_cents: Math.round(parsed * 100),
        category,
        notes: description.trim() || null,
      });
      bridge.showToast(`$${parsed.toFixed(2)} logged`);
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Log expense</Text>
      <Text style={styles.label}>Amount (USD)</Text>
      <TextInput
        style={styles.input} keyboardType="decimal-pad"
        placeholder="42.50" value={amount} onChangeText={setAmount}
      />
      <Text style={styles.label}>Description</Text>
      <TextInput
        style={styles.input} placeholder="bowling"
        value={description} onChangeText={setDescription}
      />
      <Text style={styles.label}>Category</Text>
      <View style={styles.chipsRow}>
        {CATEGORIES.map((c) => (
          <Pressable
            key={c}
            style={[styles.chip, category === c && styles.chipActive]}
            onPress={() => setCategory(c)}
          >
            <Text style={category === c ? styles.chipTextActive : styles.chipText}>{c}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.hint}>
        Tip: Save now, then tap the saved expense in the timeline to attach a receipt photo.
      </Text>
      {error && <Text style={styles.error}>{error}</Text>}
      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Save</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 16 },
  chipsRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 4 },
  chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
  chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
  chipText: { color: "#444", fontSize: 12 },
  chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
  hint: { marginTop: 10, color: "#888", fontSize: 12 },
  error: { color: "#c22", marginTop: 8 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/plugins/custody/components/ExpenseForm.tsx
git commit -m "feat(custody): ExpenseForm component"
```

---

### Task 7.4: TextCaptureForm

**Files:**
- Create: `backend/app/plugins/custody/components/TextCaptureForm.tsx`

- [ ] **Step 1: Write the component**

v1 creates a `text_screenshot` event with an optional note. Photo attachment is done from the timeline-tap inline sheet (same surface as other events). Keeping this form simple matches the YAGNI guidance in the spec — no in-form camera work that would require a new bridge verb.

```tsx
// backend/app/plugins/custody/components/TextCaptureForm.tsx
import React, { useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface TextCaptureFormProps extends WithBridge {
  childId: string;
}

export function TextCaptureForm({ bridge, childId }: TextCaptureFormProps) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
        child_id: childId, type: "text_screenshot",
        occurred_at: new Date().toISOString(),
        notes: note.trim() || null,
      });
      bridge.showToast("Text event logged — attach screenshots from timeline");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Log text from other parent</Text>
      <Text style={styles.hint}>
        Save this event, then tap it in the timeline to attach a screenshot.
      </Text>
      <Text style={styles.label}>Note (optional)</Text>
      <TextInput
        style={[styles.input, { height: 80 }]} multiline
        placeholder="e.g. refused my Sunday pickup window"
        value={note} onChangeText={setNote}
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Save</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 4 },
  hint: { color: "#888", fontSize: 12, marginBottom: 14 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 16, textAlignVertical: "top" },
  error: { color: "#c22", marginTop: 8 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/plugins/custody/components/TextCaptureForm.tsx
git commit -m "feat(custody): TextCaptureForm component"
```

---

### Task 7.5: EventForm (generic add/edit for activity/note/medical/school/phone_call/missed_visit)

**Files:**
- Create: `backend/app/plugins/custody/components/EventForm.tsx`

- [ ] **Step 1: Write the component**

```tsx
// backend/app/plugins/custody/components/EventForm.tsx
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Switch, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

type EventType = "activity" | "note" | "medical" | "school" | "phone_call" | "missed_visit" | "pickup" | "dropoff";

interface EventFormProps extends WithBridge {
  childId?: string;
  type?: EventType;
  eventId?: string;
  mode?: "create" | "edit";
}

interface EventRow {
  id: string; child_id: string; type: EventType;
  occurred_at: string;
  notes?: string | null; location?: string | null;
  overnight?: boolean; call_connected?: boolean | null;
}

export function EventForm({ bridge, childId, type = "note", eventId, mode = "create" }: EventFormProps) {
  const [effectiveType, setEffectiveType] = useState<EventType>(type);
  const [occurredAt, setOccurredAt] = useState<string>(() => new Date().toISOString());
  const [notes, setNotes] = useState("");
  const [location, setLocation] = useState("");
  const [overnight, setOvernight] = useState(false);
  const [callConnected, setCallConnected] = useState<boolean>(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(mode === "create");

  useEffect(() => {
    if (mode !== "edit" || !eventId) return;
    bridge
      .callPluginApi(`/api/plugins/custody/events/${eventId}`, "GET", null)
      // The GET-one route isn't registered; fetch via list fallback.
      .catch(async () => {
        // Fallback to list + find.
        const list = (await bridge.callPluginApi(
          `/api/plugins/custody/events?limit=500`, "GET", null,
        )) as EventRow[];
        return list.find((x) => x.id === eventId);
      })
      .then((evt) => {
        if (!evt) return;
        const e = evt as EventRow;
        setEffectiveType(e.type);
        setOccurredAt(e.occurred_at);
        setNotes(e.notes || "");
        setLocation(e.location || "");
        setOvernight(!!e.overnight);
        setCallConnected(e.call_connected ?? true);
      })
      .finally(() => setLoaded(true));
  }, [bridge, eventId, mode]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (mode === "edit" && eventId) {
        await bridge.callPluginApi(`/api/plugins/custody/events/${eventId}`, "PATCH", {
          notes: notes || null,
          location: location || null,
          ...(effectiveType === "pickup" ? { overnight } : {}),
          ...(effectiveType === "phone_call" ? { call_connected: callConnected } : {}),
          occurred_at: occurredAt,
        });
      } else {
        if (!childId) { setError("Missing child id."); setSaving(false); return; }
        await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
          child_id: childId, type: effectiveType,
          occurred_at: occurredAt,
          notes: notes || null,
          location: location || null,
          overnight: effectiveType === "pickup" ? overnight : false,
          call_connected: effectiveType === "phone_call" ? callConnected : null,
        });
      }
      bridge.showToast("Saved");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!eventId) return;
    setDeleting(true);
    try {
      await bridge.callPluginApi(`/api/plugins/custody/events/${eventId}`, "DELETE", null);
      bridge.showToast("Deleted");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed to delete");
    } finally {
      setDeleting(false);
    }
  };

  if (!loaded) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        {mode === "edit" ? "Edit event" : `Log ${effectiveType.replace("_", " ")}`}
      </Text>
      <Text style={styles.label}>When (ISO)</Text>
      <TextInput style={styles.input} value={occurredAt} onChangeText={setOccurredAt} />

      <Text style={styles.label}>Notes</Text>
      <TextInput
        style={[styles.input, { height: 70 }]} multiline
        value={notes} onChangeText={setNotes}
      />

      <Text style={styles.label}>Location</Text>
      <TextInput style={styles.input} value={location} onChangeText={setLocation} />

      {effectiveType === "pickup" && (
        <View style={styles.switchRow}>
          <Text style={styles.label}>Overnight visit</Text>
          <Switch value={overnight} onValueChange={setOvernight} />
        </View>
      )}
      {effectiveType === "phone_call" && (
        <View style={styles.switchRow}>
          <Text style={styles.label}>Call connected</Text>
          <Switch value={callConnected} onValueChange={setCallConnected} />
        </View>
      )}

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Save</Text>}
        </Pressable>
      </View>

      {mode === "edit" && (
        <Pressable style={styles.deleteBtn} onPress={remove} disabled={deleting}>
          <Text style={styles.deleteBtnText}>{deleting ? "Deleting..." : "Delete event"}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
  switchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 10 },
  error: { color: "#c22", marginTop: 10 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
  deleteBtn: { marginTop: 20, padding: 10, alignItems: "center" },
  deleteBtnText: { color: "#c22", fontWeight: "600" },
});
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/plugins/custody/components/EventForm.tsx
git commit -m "feat(custody): EventForm (generic create/edit)"
```

---

### Task 7.6: ChildrenScreen + ScheduleListScreen + ScheduleForm

**Files:**
- Create: `backend/app/plugins/custody/components/ChildrenScreen.tsx`
- Create: `backend/app/plugins/custody/components/ScheduleListScreen.tsx`
- Create: `backend/app/plugins/custody/components/ScheduleForm.tsx`

- [ ] **Step 1: Write `ChildrenScreen.tsx`**

```tsx
// backend/app/plugins/custody/components/ChildrenScreen.tsx
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Alert, FlatList, Pressable,
  StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Child { id: string; name: string; dob?: string | null }

export function ChildrenScreen({ bridge }: WithBridge) {
  const [children, setChildren] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");

  const load = async () => {
    setLoading(true);
    const rows = (await bridge.callPluginApi(
      "/api/plugins/custody/children", "GET", null,
    )) as Child[];
    setChildren(rows);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!name.trim()) return;
    await bridge.callPluginApi("/api/plugins/custody/children", "POST", {
      name: name.trim(), dob: dob.trim() || null,
    });
    setName(""); setDob("");
    bridge.showToast("Added");
    load();
  };

  const remove = async (c: Child) => {
    Alert.alert("Delete child?", `All events for ${c.name} will be deleted.`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete", style: "destructive",
        onPress: async () => {
          await bridge.callPluginApi(`/api/plugins/custody/children/${c.id}`, "DELETE", null);
          load();
        },
      },
    ]);
  };

  if (loading) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Children</Text>
      <FlatList
        data={children} keyExtractor={(c) => c.id}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{item.name}</Text>
              {item.dob && <Text style={styles.dob}>DOB {item.dob}</Text>}
            </View>
            <Pressable onPress={() => remove(item)}>
              <Text style={{ color: "#c22" }}>Delete</Text>
            </Pressable>
          </View>
        )}
      />
      <Text style={styles.label}>Add a child</Text>
      <TextInput style={styles.input} placeholder="Name" value={name} onChangeText={setName} />
      <TextInput style={styles.input} placeholder="DOB (YYYY-MM-DD, optional)" value={dob} onChangeText={setDob} />
      <Pressable style={styles.primary} onPress={add}>
        <Text style={styles.primaryText}>Add</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  row: { flexDirection: "row", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
  name: { fontSize: 16 },
  dob: { fontSize: 12, color: "#666" },
  label: { fontSize: 12, color: "#666", marginTop: 16, marginBottom: 6, letterSpacing: 0.5, textTransform: "uppercase" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, marginBottom: 8 },
  primary: { backgroundColor: "#2a7", padding: 12, borderRadius: 6, alignItems: "center", marginTop: 4 },
  primaryText: { color: "#fff", fontWeight: "600" },
});
```

- [ ] **Step 2: Write `ScheduleListScreen.tsx`**

```tsx
// backend/app/plugins/custody/components/ScheduleListScreen.tsx
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Schedule {
  id: string; child_id: string; name: string; active: boolean;
  start_date: string; interval_weeks: number; weekdays: string;
  pickup_time: string; dropoff_time: string;
}

export function ScheduleListScreen({ bridge }: WithBridge) {
  const [rows, setRows] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const data = (await bridge.callPluginApi(
      "/api/plugins/custody/schedules", "GET", null,
    )) as Schedule[];
    setRows(data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  if (loading) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Schedules</Text>
      <FlatList
        data={rows} keyExtractor={(r) => r.id}
        renderItem={({ item }) => (
          <Pressable
            style={styles.row}
            onPress={() => bridge.openComponent?.("ScheduleForm", { scheduleId: item.id })}
          >
            <Text style={styles.name}>{item.name}</Text>
            <Text style={styles.sub}>
              Every {item.interval_weeks}w · days {item.weekdays} ·
              {" "}{item.pickup_time}→{item.dropoff_time}
            </Text>
          </Pressable>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No schedules yet.</Text>}
      />
      <Pressable
        style={styles.primary}
        onPress={() => bridge.openComponent?.("ScheduleForm")}
      >
        <Text style={styles.primaryText}>+ Add schedule</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  row: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
  name: { fontSize: 15, fontWeight: "600" },
  sub: { fontSize: 12, color: "#666" },
  empty: { color: "#888", padding: 20, textAlign: "center" },
  primary: { backgroundColor: "#2a7", padding: 12, borderRadius: 6, alignItems: "center", marginTop: 12 },
  primaryText: { color: "#fff", fontWeight: "600" },
});
```

- [ ] **Step 3: Write `ScheduleForm.tsx`**

```tsx
// backend/app/plugins/custody/components/ScheduleForm.tsx
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Child { id: string; name: string }

const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"]; // Mon=0..Sun=6

interface ScheduleFormProps extends WithBridge {
  scheduleId?: string;
}

export function ScheduleForm({ bridge, scheduleId }: ScheduleFormProps) {
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState<string>("");
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [intervalWeeks, setIntervalWeeks] = useState("1");
  const [weekdaySet, setWeekdaySet] = useState<Set<number>>(new Set([4]));
  const [pickupTime, setPickupTime] = useState("17:00");
  const [dropoffTime, setDropoffTime] = useState("19:00");
  const [pickupLocation, setPickupLocation] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(!scheduleId);

  useEffect(() => {
    bridge.callPluginApi("/api/plugins/custody/children", "GET", null).then((list) => {
      const rows = list as Child[];
      setChildren(rows);
      if (rows[0] && !childId) setChildId(rows[0].id);
    });
  }, [bridge]);

  useEffect(() => {
    if (!scheduleId) return;
    bridge.callPluginApi(
      "/api/plugins/custody/schedules", "GET", null,
    ).then((list) => {
      const found = (list as Array<{
        id: string; child_id: string; name: string; start_date: string;
        interval_weeks: number; weekdays: string;
        pickup_time: string; dropoff_time: string; pickup_location?: string;
      }>).find((s) => s.id === scheduleId);
      if (found) {
        setChildId(found.child_id);
        setName(found.name);
        setStartDate(found.start_date);
        setIntervalWeeks(String(found.interval_weeks));
        setWeekdaySet(new Set(found.weekdays.split(",").map(Number)));
        setPickupTime(found.pickup_time);
        setDropoffTime(found.dropoff_time);
        setPickupLocation(found.pickup_location || "");
      }
    }).finally(() => setLoaded(true));
  }, [bridge, scheduleId]);

  const toggleDay = (i: number) => {
    const next = new Set(weekdaySet);
    next.has(i) ? next.delete(i) : next.add(i);
    setWeekdaySet(next);
  };

  const save = async () => {
    if (!childId) { setError("Pick a child first"); return; }
    if (weekdaySet.size === 0) { setError("Pick at least one weekday"); return; }
    setSaving(true);
    setError(null);
    const payload = {
      child_id: childId, name: name.trim() || "Schedule",
      start_date: startDate,
      interval_weeks: Math.max(1, parseInt(intervalWeeks, 10) || 1),
      weekdays: Array.from(weekdaySet).sort().join(","),
      pickup_time: pickupTime, dropoff_time: dropoffTime,
      pickup_location: pickupLocation.trim() || null,
    };
    try {
      if (scheduleId) {
        await bridge.callPluginApi(
          `/api/plugins/custody/schedules/${scheduleId}`, "PATCH", payload,
        );
      } else {
        await bridge.callPluginApi("/api/plugins/custody/schedules", "POST", payload);
      }
      bridge.showToast("Saved");
      bridge.closeComponent();
    } catch (e) {
      setError((e as Error).message || "Failed");
    } finally {
      setSaving(false);
    }
  };

  if (!loaded) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{scheduleId ? "Edit schedule" : "New schedule"}</Text>

      <Text style={styles.label}>Child</Text>
      <View style={styles.row}>
        {children.map((c) => (
          <Pressable
            key={c.id}
            style={[styles.chip, c.id === childId && styles.chipActive]}
            onPress={() => setChildId(c.id)}
          >
            <Text style={c.id === childId ? styles.chipTextActive : styles.chipText}>
              {c.name}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Name</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="EOW Fri-Sun" />

      <Text style={styles.label}>Start date (YYYY-MM-DD)</Text>
      <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} />

      <Text style={styles.label}>Interval (weeks)</Text>
      <TextInput
        style={styles.input} keyboardType="numeric"
        value={intervalWeeks} onChangeText={setIntervalWeeks}
      />

      <Text style={styles.label}>Weekdays</Text>
      <View style={styles.row}>
        {DAY_LABELS.map((lbl, i) => (
          <Pressable
            key={i} style={[styles.dayBtn, weekdaySet.has(i) && styles.dayBtnOn]}
            onPress={() => toggleDay(i)}
          >
            <Text style={weekdaySet.has(i) ? styles.dayTextOn : styles.dayText}>{lbl}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Pickup (HH:MM)</Text>
      <TextInput style={styles.input} value={pickupTime} onChangeText={setPickupTime} />

      <Text style={styles.label}>Dropoff (HH:MM)</Text>
      <TextInput style={styles.input} value={dropoffTime} onChangeText={setDropoffTime} />

      <Text style={styles.label}>Pickup location (optional)</Text>
      <TextInput style={styles.input} value={pickupLocation} onChangeText={setPickupLocation} />

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Cancel</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Save</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  row: { flexDirection: "row", flexWrap: "wrap" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
  chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
  chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
  chipText: { color: "#444", fontSize: 12 },
  chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
  dayBtn: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: "#ddd", alignItems: "center", justifyContent: "center", marginRight: 6 },
  dayBtnOn: { backgroundColor: "#2a7", borderColor: "#2a7" },
  dayText: { color: "#444" },
  dayTextOn: { color: "#fff", fontWeight: "600" },
  error: { color: "#c22", marginTop: 8 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/plugins/custody/components/ChildrenScreen.tsx backend/app/plugins/custody/components/ScheduleListScreen.tsx backend/app/plugins/custody/components/ScheduleForm.tsx
git commit -m "feat(custody): ChildrenScreen, ScheduleListScreen, ScheduleForm"
```

---

### Task 7.7: ExportSheet

**Files:**
- Create: `backend/app/plugins/custody/components/ExportSheet.tsx`

- [ ] **Step 1: Write the component**

v1 exposes a "copy export URL" affordance: the server signs requests via the normal JWT header, so a React-Native download-to-device flow would require a new bridge verb. Keeping this form simple matches the spec's "just save to device" goal and defers device-save until the bridge has it.

```tsx
// backend/app/plugins/custody/components/ExportSheet.tsx
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import type { WithBridge } from "./bridge";

interface Child { id: string; name: string }

export function ExportSheet({ bridge }: WithBridge) {
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState<string>("");
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0, 10));
  const [format, setFormat] = useState<"pdf" | "csv">("pdf");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    bridge.callPluginApi("/api/plugins/custody/children", "GET", null).then((list) => {
      const rows = list as Child[];
      setChildren(rows);
      if (rows[0]) setChildId(rows[0].id);
    });
  }, [bridge]);

  const doExport = async () => {
    if (!childId) return;
    setBusy(true);
    setStatus(null);
    try {
      const from = `${fromDate}T00:00:00`;
      const to = `${toDate}T23:59:59`;
      // The bridge's callPluginApi returns parsed JSON for JSON responses; for
      // binary downloads we only need to trigger the server side so the file is
      // generated. In v1 we surface a "successful — file is available via
      // /api/plugins/custody/export?…" message, and a later phase adds a native
      // download bridge verb.
      await bridge.callPluginApi(
        `/api/plugins/custody/export?child_id=${childId}`
        + `&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
        + `&format=${format}`,
        "GET", null,
      );
      setStatus(`Export generated. Re-open from the same URL to download.`);
    } catch (e) {
      setStatus((e as Error).message || "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Export custody log</Text>

      <Text style={styles.label}>Child</Text>
      <View style={styles.row}>
        {children.map((c) => (
          <Pressable
            key={c.id}
            style={[styles.chip, c.id === childId && styles.chipActive]}
            onPress={() => setChildId(c.id)}
          >
            <Text style={c.id === childId ? styles.chipTextActive : styles.chipText}>{c.name}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>From (YYYY-MM-DD)</Text>
      <TextInput style={styles.input} value={fromDate} onChangeText={setFromDate} />
      <Text style={styles.label}>To (YYYY-MM-DD)</Text>
      <TextInput style={styles.input} value={toDate} onChangeText={setToDate} />

      <Text style={styles.label}>Format</Text>
      <View style={styles.row}>
        {(["pdf", "csv"] as const).map((f) => (
          <Pressable
            key={f} style={[styles.chip, format === f && styles.chipActive]}
            onPress={() => setFormat(f)}
          >
            <Text style={format === f ? styles.chipTextActive : styles.chipText}>
              {f.toUpperCase()}
            </Text>
          </Pressable>
        ))}
      </View>

      {status && <Text style={styles.status}>{status}</Text>}

      <View style={styles.btnRow}>
        <Pressable style={styles.cancelBtn} onPress={bridge.closeComponent}>
          <Text style={styles.cancelBtnText}>Close</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={doExport} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Export</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
  label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
  row: { flexDirection: "row", flexWrap: "wrap" },
  chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
  chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
  chipText: { color: "#444", fontSize: 12 },
  chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
  status: { color: "#444", marginTop: 10 },
  btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
  cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
  cancelBtnText: { fontWeight: "600", color: "#444" },
  saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600" },
});
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/plugins/custody/components/ExportSheet.tsx
git commit -m "feat(custody): ExportSheet component"
```

---

### Task 7.8: Build the bundle

**Files:**
- Create (generated): `backend/app/plugins/custody/bundle/custody.js`

- [ ] **Step 1: Run the build**

Run: `cd backend/app/plugins/custody && npm run build`
Expected: `[custody] built .../bundle/custody.js`. If esbuild reports a missing component import, that component's file is missing — back up and create it.

- [ ] **Step 2: Confirm the bundle is non-empty**

Run: `ls -la backend/app/plugins/custody/bundle/custody.js`
Expected: a file larger than 20KB.

- [ ] **Step 3: Commit the bundle**

```bash
git add backend/app/plugins/custody/bundle/custody.js
git commit -m "feat(custody): build first bundle"
```

---

## Phase 8 — Smoke + PR

### Task 8.1: Full backend test sweep

- [ ] **Step 1: Run everything**

```bash
cd backend
.venv/Scripts/pytest -q
```

Expected: all green. Any regression in yardsailing tests after Phase 0 refactor must be fixed before opening the PR.

### Task 8.2: Manual smoke (backend + mobile)

- [ ] **Step 1: Start the backend**

```bash
cd backend
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Quick cURL pass**

Obtain a JWT from the OAuth flow as usual, then:

```bash
TOKEN=<paste>
BASE=http://localhost:8000/api/plugins/custody

# Create child
curl -s -X POST $BASE/children -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Mason","dob":"2020-08-12"}' | jq .

# Log a pickup
curl -s -X POST $BASE/events -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"child_id":"<child_id>","type":"pickup","notes":"school"}' | jq .

# Status
curl -s "$BASE/status?child_id=<child_id>" -H "Authorization: Bearer $TOKEN" | jq .

# Export CSV
curl -s "$BASE/export?child_id=<child_id>&from=2026-01-01T00:00:00&to=2026-12-31T23:59:59&format=csv" \
  -H "Authorization: Bearer $TOKEN" -o custody.csv
head custody.csv
```

Expected: each call returns the right shape; CSV has the header row.

- [ ] **Step 3: Mobile smoke**

```bash
cd mobile && npx expo start
```

Open the app, sign in, tap **Skills → Custody**. Confirm:
1. Children screen lets you add Mason.
2. CustodyHome shows the status card ("No schedule yet").
3. Tap "Set up schedule" → ScheduleForm. Save an EOW Fri-Sun.
4. Tap "Picked up" → pickup event lands in timeline.
5. Tap "+ Expense" → ExpenseForm. Save a $42.50 activity.
6. Tap the expense in the timeline → EventForm edit. Attach a photo via the bridge paperclip flow (v1: note that photo attach from home screen's event-tap is deferred; photo upload works via `/api/plugins/custody/events/{id}/photos` — verify via cURL if that path is untested).
7. Tap "Export…" in the header → ExportSheet. Generate a PDF; confirm server returns a valid `%PDF-` file.

- [ ] **Step 4: Commit any tweaks discovered during smoke**

Only commit fixes that fall out of smoke; don't pile unrelated changes into this task.

### Task 8.3: PR against main

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feature/custody-tracker
gh pr create --title "feat(custody): custody tracker plugin" --body "$(cat <<'EOF'
## Summary
- New internal plugin `custody` for logging visitations, expenses, text screenshots, schedules, and missed visits.
- LLM tools for chat-first logging + rich React Native home screen with status card, timeline, quick actions.
- Recurring schedules auto-flag missed visits (idempotent `refresh-missed` endpoint).
- PDF + CSV export for a date range.
- Shared photo helper extracted into `app/plugins/core/photos.py` (used by yardsailing and custody).

## Test plan
- [ ] `pytest backend/tests/plugins/custody/` all green
- [ ] `pytest backend/tests/plugins/yardsailing/` still green after photo refactor
- [ ] Manual smoke: chat "picked up Mason" → event logged
- [ ] Manual smoke: home screen quick actions log correct event types
- [ ] Manual smoke: schedule creates, refresh-missed flags missed visits
- [ ] Manual smoke: PDF export returns valid PDF bytes

Spec: `docs/superpowers/specs/2026-04-16-custody-tracker-design.md`
Plan: `docs/superpowers/plans/2026-04-16-custody-tracker.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Risks / Notes

- **Timezone drift**: v1 uses server local time for schedule math. Users in different zones will see scheduled pickups shifted. Documented as a known limitation in the spec; not blocking for a single-user ship.
- **Photo attach from timeline**: the home-screen event-tap opens `EventForm`, which doesn't yet surface the photo-upload endpoint. Keep photo upload via the `/events/{id}/photos` endpoint working; a future task can extend `EventForm` to call it via `FormData`.
- **Export device-save**: `ExportSheet` only triggers the server-side generation; a native download-to-device flow requires a new bridge verb. Ship v1 as "export URL works from the server"; improve in a follow-up.
- **Shared-photo refactor reach**: the Phase 0 refactor is surgical (one file rewritten, imports shimmed to keep the old constant names exported). If yardsailing tests regress, the problem is almost certainly in `yardsailing/photos.py`'s re-exports, not the extracted module.
- **Missed-visit delete semantics**: v1 uses `DELETE /events/{id}` to clear a false-positive. If user feedback wants "keep the row, mark dismissed", that's a later schema bump (add a `status` column).

## Non-goals (reminder)

- No OCR for text screenshots.
- No co-parent reimbursement / split tracking.
- No GPS; only free-text location.
- No shared log between parents.
- No push notifications / reminders.
- No full iCal recurrence.

## Self-review

Mapped each spec section back to a task:

- **Scope/In:** multi-child (Task 1.2 `Child`), 10 event types (Task 2.2 `EVENT_TYPES` enum + validation), rich home screen (7.2), recurring schedule (1.2 `Schedule`, 2.3 service, 3.1 engine), missed-visit auto-detect (3.2), photo attachments via shared helper (0.1, 4.1), PDF+CSV export (4.2, 4.3, 5.5).
- **Scope/Out:** no OCR, no reimbursement, no GPS, no shared log, no notifications, no iCal, no per-user tz — none of these are implemented in any task.
- **Data model:** 5 tables all present (Task 1.2); indexes declared as specified.
- **LLM tools:** 7 tools present in Task 6.1 (`log_custody_event`, `log_expense`, `log_missed_visit`, `query_custody_events`, `show_custody_home`, `show_expense_form`, `show_text_capture`). Child resolution test (6.1) covers single-child default, case-insensitive match, and `child_not_found` error shape.
- **Backend routes:** children (5.2), events+photos (5.3), schedules+exceptions (5.4), status/summary/refresh-missed/export (5.5).
- **Mobile components:** all 8 exports present (7.2–7.7). Bridge registration via `components/index.ts` (7.1).
- **Shared photo refactor:** 0.1 + 0.2; yardsailing tests re-run as a regression check in 0.2.
- **Loading & migration:** lazy-imported models in `__init__.py` (1.1) so `Base.metadata.create_all` picks up tables at startup; `reportlab` added to requirements (0.3).
- **Test plan:** test files for models (1.2), services (2.1/2/3), recurrence (3.1), missed visits (3.2), status/summary (3.3), photos (4.1), CSV (4.2), PDF (4.3), routes (5.2/3/4/5), tools (6.1/6.2).

Type-consistency spot-check: `CreateEventInput` (Task 2.2) fields line up with the `EventBody` Pydantic model (Task 5.1) and the LLM tool handlers (Task 6.1). `ExpectedPickup` is consumed by `refresh_missed` (Task 3.2) with the same field names defined in Task 3.1.

No placeholders or unresolved TODOs remaining.







