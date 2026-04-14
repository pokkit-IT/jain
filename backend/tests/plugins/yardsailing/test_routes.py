import io
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.auth.jwt import sign_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User


_SALE_PAYLOAD = {
    "title": "Photo Sale", "address": "1 Test St",
    "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
    "description": None, "end_date": None,
}


async def _create_test_sale(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json=_SALE_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _make_jpeg_buf() -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (100, 200, 50)).save(buf, format="JPEG")
    buf.seek(0)
    return buf


@pytest.fixture
async def app_and_token():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = sign_access_token(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token


async def test_post_sales_requires_auth(app_and_token):
    client, _ = app_and_token
    resp = await client.post("/api/plugins/yardsailing/sales", json={
        "title": "s", "address": "a",
        "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
    })
    assert resp.status_code == 401


async def test_post_sales_creates_row(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Big Sale", "address": "123 Main",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Big Sale"
    assert "id" in body


async def test_post_sales_returns_geocoded_coords(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Pinned", "address": "123 Main",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    # The conftest autouse stub returns (40.0, -74.0).
    assert body["lat"] == 40.0
    assert body["lng"] == -74.0


async def test_recent_sales_is_public_and_returns_pins(app_and_token):
    client, token = app_and_token
    await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Public Pin", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/plugins/yardsailing/sales/recent")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["lat"] == 40.0
    assert rows[0]["lng"] == -74.0


async def test_tags_are_stored_and_returned(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Kids Stuff", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
            "tags": ["Toys", "Baby Items", "toys"],  # dupe should collapse
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert set(body["tags"]) == {"toys", "baby items"}


async def test_recent_sales_filters_by_tag(app_and_token):
    client, token = app_and_token
    for title, tags in [("A", ["Tools"]), ("B", ["Toys"]), ("C", ["Tools", "Clothing"])]:
        await client.post(
            "/api/plugins/yardsailing/sales",
            json={
                "title": title, "address": "a",
                "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
                "description": None, "end_date": None, "tags": tags,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get("/api/plugins/yardsailing/sales/recent?tag=tools")
    titles = {r["title"] for r in resp.json()}
    assert titles == {"A", "C"}


async def test_recent_sales_text_search_hits_description(app_and_token):
    client, token = app_and_token
    await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Random", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": "lots of vintage cameras", "end_date": None, "tags": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/plugins/yardsailing/sales/recent?q=camera")
    assert len(resp.json()) == 1


async def test_single_day_sale_returns_one_day_entry(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "One Day", "address": "a",
            "start_date": "2026-04-18", "end_date": None,
            "start_time": "08:00", "end_time": "14:00",
            "description": None, "tags": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["days"] == [
        {"day_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00"},
    ]


async def test_multi_day_expands_with_defaults_when_no_overrides(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Three Day", "address": "a",
            "start_date": "2026-04-18", "end_date": "2026-04-20",
            "start_time": "08:00", "end_time": "14:00",
            "description": None, "tags": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    dates = [d["day_date"] for d in body["days"]]
    assert dates == ["2026-04-18", "2026-04-19", "2026-04-20"]
    assert all(d["start_time"] == "08:00" and d["end_time"] == "14:00" for d in body["days"])


async def test_multi_day_respects_per_day_overrides(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Varying Hours", "address": "a",
            "start_date": "2026-04-18", "end_date": "2026-04-20",
            "start_time": "08:00", "end_time": "14:00",
            "description": None, "tags": [],
            "days": [
                {"day_date": "2026-04-19", "start_time": "10:00", "end_time": "16:00"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    days = {d["day_date"]: (d["start_time"], d["end_time"]) for d in body["days"]}
    assert days["2026-04-18"] == ("08:00", "14:00")
    assert days["2026-04-19"] == ("10:00", "16:00")
    assert days["2026-04-20"] == ("08:00", "14:00")


async def test_tags_endpoint_lists_curated_vocab(app_and_token):
    client, _ = app_and_token
    resp = await client.get("/api/plugins/yardsailing/tags")
    assert resp.status_code == 200
    tags = resp.json()["tags"]
    assert "Toys" in tags
    assert "Baby Items" in tags


async def test_plugin_help_includes_yardsailing(app_and_token):
    client, _ = app_and_token
    resp = await client.get("/api/plugins/help")
    assert resp.status_code == 200
    plugins = resp.json()["plugins"]
    ys = next((p for p in plugins if p["name"] == "yardsailing"), None)
    assert ys is not None
    # help.md should be loaded
    assert "Yardsailing" in ys["help_markdown"]
    # examples from plugin.json should be surfaced
    assert len(ys["examples"]) >= 1
    assert "prompt" in ys["examples"][0]


async def test_delete_sale_removes_row(app_and_token):
    client, token = app_and_token
    created = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Gone", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    sale_id = created.json()["id"]

    resp = await client.delete(
        f"/api/plugins/yardsailing/sales/{sale_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    missing = await client.get(f"/api/plugins/yardsailing/sales/{sale_id}")
    assert missing.status_code == 404


async def test_update_sale_changes_fields_and_regeocodes(app_and_token):
    client, token = app_and_token
    created = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Old Title", "address": "old addr",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    sale_id = created.json()["id"]

    resp = await client.put(
        f"/api/plugins/yardsailing/sales/{sale_id}",
        json={
            "title": "New Title", "address": "new addr",
            "start_date": "2026-04-19", "start_time": "09:00", "end_time": "15:00",
            "description": "updated", "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "New Title"
    assert body["address"] == "new addr"
    # Stubbed geocode returns (40.0, -74.0)
    assert body["lat"] == 40.0
    assert body["lng"] == -74.0


async def test_get_my_sales_lists_own_rows(app_and_token):
    client, token = app_and_token
    await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "One", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        "/api/plugins/yardsailing/sales",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["title"] == "One"


@pytest.mark.asyncio
async def test_upload_photo_endpoint_happy(app_and_token, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    client, token = app_and_token

    sale_id = await _create_test_sale(client, token)

    resp = await client.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/photos",
        files={"file": ("x.jpg", _make_jpeg_buf(), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["position"] == 0
    assert body["url"].startswith("/uploads/sales/")
    assert body["thumb_url"].startswith("/uploads/sales/")
    assert body["content_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_upload_photo_endpoint_non_owner_forbidden(app_and_two_tokens, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    app, token_a, token_b = app_and_two_tokens

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # User A creates a sale
        sale_id = await _create_test_sale(client, token_a)

        # User B tries to upload to it
        resp = await client.post(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos",
            files={"file": ("x.jpg", _make_jpeg_buf(), "image/jpeg")},
            headers={"Authorization": f"Bearer {token_b}"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_photo_endpoint(app_and_token, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    client, token = app_and_token

    sale_id = await _create_test_sale(client, token)
    buf = _make_jpeg_buf()

    up = await client.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/photos",
        files={"file": ("x.jpg", buf, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert up.status_code == 200
    photo = up.json()

    orig_abs = tmp_path / photo["url"].removeprefix("/uploads/")
    thumb_abs = tmp_path / photo["thumb_url"].removeprefix("/uploads/")
    assert orig_abs.exists() and thumb_abs.exists()

    resp = await client.delete(
        f"/api/plugins/yardsailing/sales/{sale_id}/photos/{photo['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    assert not orig_abs.exists()
    assert not thumb_abs.exists()


@pytest.mark.asyncio
async def test_reorder_photos_endpoint(app_and_token, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    client, token = app_and_token

    sale_id = await _create_test_sale(client, token)

    ids: list[str] = []
    for _ in range(3):
        buf = _make_jpeg_buf()
        r = await client.post(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos",
            files={"file": ("p.jpg", buf, "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        ids.append(r.json()["id"])

    reversed_ids = list(reversed(ids))
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
async def test_reorder_rejects_mismatched_ids(app_and_token, tmp_path, monkeypatch):
    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    client, token = app_and_token

    sale_id = await _create_test_sale(client, token)

    ids: list[str] = []
    for _ in range(3):
        buf = _make_jpeg_buf()
        r = await client.post(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos",
            files={"file": ("p.jpg", buf, "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        ids.append(r.json()["id"])

    resp = await client.patch(
        f"/api/plugins/yardsailing/sales/{sale_id}/photos/reorder",
        json={"photo_ids": ids[:2]},  # missing one
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_photo_non_owner_forbidden(app_and_two_tokens, tmp_path, monkeypatch):
    from httpx import ASGITransport as _ASGITransport

    monkeypatch.setattr("app.plugins.yardsailing.photos.UPLOADS_ROOT", tmp_path)
    app, token_a, token_b = app_and_two_tokens

    async with AsyncClient(
        transport=_ASGITransport(app=app), base_url="http://test"
    ) as client_a:
        sale_id = await _create_test_sale(client_a, token_a)
        buf = _make_jpeg_buf()
        up = await client_a.post(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos",
            files={"file": ("x.jpg", buf, "image/jpeg")},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        photo = up.json()

    async with AsyncClient(
        transport=_ASGITransport(app=app), base_url="http://test"
    ) as client_b:
        resp = await client_b.delete(
            f"/api/plugins/yardsailing/sales/{sale_id}/photos/{photo['id']}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
    assert resp.status_code in (403, 404)
