# Yardsailing Sale Photos — Design Spec

**Date:** 2026-04-14
**Status:** Approved (pending user review of written spec)
**Plugin:** yardsailing (internal)

## Goal

Let a sale's host attach up to five photos per sale. Buyers see a hero thumbnail in the in-chat list card and a full-size carousel in the sale details modal. Photos live on the backend filesystem with server-generated thumbnails; storage can be swapped for GCS or Drive later without changing the data model.

## Scope

- **Host-only uploads.** Create-time or anytime via an edit-photos flow.
- **Cap:** 5 photos per sale.
- **Storage:** local filesystem at `backend/uploads/sales/<sale_id>/<uuid>.<ext>`, served via FastAPI `StaticFiles`.
- **Thumbnails:** server-generated on upload using Pillow, ~300 px long edge, JPEG quality 80, stored alongside the original as `<uuid>-thumb.jpg`.
- **Ordering:** explicit `position` field; first photo (`position=0`) is the "hero."
- **Cascade:** deleting a sale removes its folder; deleting a single photo removes both files.

## User Flow

### Host — create sale

`SaleForm` gains a "Photos (N/5)" section after existing fields. An empty grid of thumbnail tiles plus a "+" tile. Tapping "+" opens `expo-image-picker`, adds a local preview. Reorder/remove before submit. On submit: sale is created first, then each photo uploads sequentially to the photo endpoint. Per-photo progress is shown. Upload failures keep the sale and let the user retry.

### Host — manage photos after create

`SaleDetailsModal` shows a "Manage Photos" button when `sale.owner_id === current_user.id`. Same grid UI as create-time, plus delete and reorder (up/down arrows for v1; drag-and-drop is a follow-up). Every action hits the backend immediately.

### Buyer — view

- `DataCard` map branch renders a 56×56 thumbnail on the left of each sale row when `photos[0].thumb_url` is present. No thumbnail → current layout unchanged.
- `SaleDetailsModal` adds a horizontal `ScrollView` carousel of full-size photos above existing details. Zoom/pan is out of scope for v1.

## Architecture

### Backend

**New model** — `backend/app/plugins/yardsailing/models.py`, `SalePhoto`:

| Column         | Type         | Notes                                            |
|----------------|--------------|--------------------------------------------------|
| `id`           | `str(36)` PK | UUID4                                            |
| `sale_id`      | `str(36)` FK | References `sales.id`, `ON DELETE CASCADE`       |
| `position`     | `int`        | 0-based, unique per `sale_id`                    |
| `original_path`| `str(512)`   | Relative to `uploads/` root                      |
| `thumb_path`   | `str(512)`   | Relative to `uploads/` root                      |
| `content_type` | `str(64)`    | `image/jpeg`, `image/png`, or `image/webp`       |
| `created_at`   | `datetime`   |                                                  |

Imported from `app/models/__init__.py` so `create_all()` picks it up (matches the Phase 3 pattern).

**New module** — `backend/app/plugins/yardsailing/photos.py`:
- `async def save_photo(db, sale_id, upload_file) -> SalePhoto` — validates content-type and size, writes original to disk, generates thumbnail via Pillow, inserts the row, returns it.
- `async def delete_photo(db, photo) -> None` — removes both files, deletes the row.
- `def generate_thumbnail(src_path, dst_path) -> None` — Pillow `thumbnail((300, 300))`, `save(dst_path, "JPEG", quality=80)`.
- `def sale_folder(sale_id) -> Path` — resolves `uploads/sales/<sale_id>/`.
- Sale-delete cascade: `services.delete_sale` (or the existing delete path) additionally calls `shutil.rmtree(sale_folder(sale.id), ignore_errors=True)` after DB cascade runs.

**Static mount** — in `backend/app/main.py` (or wherever routers are wired):
```python
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
```

**Endpoints** — `backend/app/plugins/yardsailing/routes.py`, all auth-required, owner-only (pattern matches existing `POST /sales`):

- `POST /api/plugins/yardsailing/sales/{sale_id}/photos` — `multipart/form-data` with a `file` field. Validates content-type in `{image/jpeg, image/png, image/webp}`, size ≤ 10 MB pre-thumbnail, cap of 5 photos per sale. Returns `SalePhoto` JSON including `url` and `thumb_url`.
- `DELETE /api/plugins/yardsailing/sales/{sale_id}/photos/{photo_id}` — removes DB row and both files.
- `PATCH /api/plugins/yardsailing/sales/{sale_id}/photos/reorder` — body `{photo_ids: [id0, id1, ...]}`. Validates that the provided IDs exactly match the sale's existing photos; rewrites `position` in list order in one transaction.

**Sale serialization** — `GET /api/plugins/yardsailing/sales` and `/sales/{id}` include a `photos: [{id, url, thumb_url, position, content_type}, ...]` array ordered by `position` (hero = index 0). URLs are built from the request base + static mount path.

**Dependency** — add `Pillow` to `backend/pyproject.toml`.

**Config** — `UPLOADS_DIR` setting with default `"uploads"`, overridable via env var for test isolation.

### Mobile

**`SaleForm.tsx`** — new section after existing fields:
- Grid of thumbnail tiles for selected photos + a single "+" tile while `photos.length < 5`.
- Tapping "+" calls `expo-image-picker` (verify it is installed; if not, add via `npx expo install expo-image-picker`).
- Reorder via up/down arrows on each tile; remove via an X corner button.
- On form submit: create the sale, then loop through photos uploading each via the photo endpoint. Per-photo spinner; on failure keep the sale and show a retry button per-photo.

**`ManagePhotosSheet.tsx`** (new) — modal sheet accessed from `SaleDetailsModal` owner actions. Same grid UI; each action (add/remove/reorder) hits the backend immediately and updates local state from the response.

**`DataCard.tsx` (map branch)** — add a 56×56 `Image` on the left of each row when `sale.photos?.[0]?.thumb_url` exists. Existing row content flexes to fill remaining space. No thumbnail → existing layout.

**`SaleDetailsModal.tsx`** — add a horizontal `ScrollView` carousel above the existing details when `sale.photos?.length > 0`. Each photo is `<Image source={{ uri: photo.url }} />` at a fixed height (e.g., 240 px). A small dot indicator below if there are ≥2 photos.

**Types** — extend `mobile/src/types.ts` `Sale`:
```ts
export interface SalePhoto {
  id: string;
  url: string;
  thumb_url: string;
  position: number;
  content_type: string;
}
export interface Sale {
  // existing fields
  photos?: SalePhoto[];
}
```

**API client** — extend `mobile/src/api/yardsailing.ts`:
- `uploadSalePhoto(saleId, file) -> Promise<SalePhoto>` — multipart POST.
- `deleteSalePhoto(saleId, photoId) -> Promise<void>`.
- `reorderSalePhotos(saleId, photoIds: string[]) -> Promise<SalePhoto[]>`.

## Testing

### Backend (pytest)

- `test_upload_photo_happy_path` — multipart POST → `SalePhoto` row created; both original and thumbnail files exist on disk; thumbnail bytes smaller than original.
- `test_upload_rejects_non_image_content_type` — `text/plain` upload returns 400.
- `test_upload_rejects_oversized_file` — file > 10 MB returns 400.
- `test_upload_rejects_over_cap` — 6th photo for a sale returns 400.
- `test_upload_requires_owner` — non-owner user gets 403.
- `test_delete_photo_removes_files_and_row` — row gone, both files gone.
- `test_delete_sale_cascades_photos` — deleting the sale removes the folder and any remaining photo rows.
- `test_reorder_photos_updates_position` — positions match supplied order; partial ID list returns 400.
- `test_sale_listing_includes_ordered_photos` — GET sale/s includes `photos[]` sorted by position, hero first.

### Mobile

No unit tests. `tsc --noEmit` must be clean. Manual QA checklist:

- Create sale with 0, 3, 5 photos.
- Try to add a 6th photo (blocked in UI).
- Upload fails (toggle airplane mode); retry works.
- Edit photos on an existing owned sale: add, remove, reorder.
- Non-owner of a sale does not see "Manage Photos."
- List card shows hero thumbnail; tapping opens detail with full carousel.
- List card without photos renders identically to the pre-feature layout.

## Out of Scope

- Buyer or third-party uploads.
- Moderation / reporting.
- EXIF / GPS metadata stripping.
- HEIC/HEIF decoding beyond what Pillow handles by default (the mobile picker converts HEIC to JPEG on iOS).
- Client-side compression before upload.
- Zoom/pan in the detail carousel.
- Signed URLs, CDN, or multi-region storage.
- Image search, face detection, tags, or any ML.
- Drag-and-drop reorder (v2 — up/down arrows for v1).

## Open Questions

- **HEIC on iOS:** `expo-image-picker` provides an `allowsEditing` / `mediaTypes` config; on recent Expo SDK versions HEIC images are auto-converted by the picker when `allowsEditing` is used or when the `PHPickerConfiguration` path is active. Verify during implementation; if HEIC leaks through, either force `Images` mode with JPEG output or have Pillow handle it via `pillow-heif`.
- **Migration of existing sales:** none needed — all existing sales will simply have an empty `photos: []` on read.
- **Future storage swap:** the `original_path`/`thumb_path` columns are filesystem-relative today; swapping to GCS or Drive means writing an uploader abstraction behind `save_photo` and changing URL construction. Not part of this spec.
