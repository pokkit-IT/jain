# Custody Tracker Plugin — Design Spec

**Date:** 2026-04-16
**Status:** Draft
**Scope:** New internal plugin `custody` + shared photo helper refactor

## Goal

A JAIN plugin for parents to log visitation events with their children — pickups, dropoffs, activities, expenses (with receipts), screenshots of texts from the other parent, medical/school events, phone calls, missed visits, and free-form notes. Primary interface is chat ("picked up Mason", "bowling $42"), with a rich home screen for photo-heavy actions and one-tap custody transitions. A recurring schedule lets the app auto-flag missed visits. An export button produces PDF + CSV for any date range — personal use first, but court-ready when it matters.

## User Story

A parent installs `custody`, adds their child (e.g. Mason, age 5), enters a recurring schedule ("EOW Fri 5pm → Sun 7pm"). From then on:

- They say "picked up Mason" in Jain chat → an event stamped at now is logged.
- They tap **+ Expense** on the home screen → camera opens, they snap the bowling receipt, type `42.50`, pick `activity` → event saved.
- At Sunday dropoff they say "dropped Mason off at 7:15 pm" → event logged with an override time.
- Mother denies the next Friday's visit → app auto-flags a missed-visit row because no pickup event landed within 2h of the scheduled time. Parent confirms.
- Six months later they tap **Export**, pick the full range, get a PDF for their lawyer.

## Scope

**In:**
- New internal plugin `custody` under `backend/app/plugins/custody/` (same tier as yardsailing).
- Multi-child support — every event references a `custody_children` row; owner-scoped.
- 10 event types (pickup, dropoff, activity, expense, text_screenshot, medical, school, missed_visit, phone_call, note) on a single polymorphic `custody_events` table; `overnight` is a bool flag on pickup rows, not its own type.
- Chat-first LLM tools + rich React Native home screen with status header, quick actions, and timeline.
- Recurring schedules (weekly / every-N-weeks, days-of-week, times) per child, plus per-date exceptions (skip / override).
- Missed-visit auto-detection (idempotent `refresh_missed` endpoint, called on home-screen focus).
- Photo attachments (receipts, text screenshots) reusing yardsailing's upload + thumbnail pattern.
- PDF + CSV export for a date range.
- Shared photo helper extraction into `app/plugins/core/photos.py` (used by both yardsailing and custody).

**Out (v2+):**
- OCR of text screenshots.
- Co-parent reimbursement / split tracking.
- GPS or map location (only free-text "where").
- Shared log with the other parent.
- Push notifications / reminders.
- Per-user timezones (v1 uses server local time; add later).
- Cross-user discovery / marketplace.

## Architecture

### Data model

All tables prefixed `custody_`. Follow the yardsailing naming convention so plugin tables can't collide with core.

**`custody_children`**
```
id (str uuid, pk)
owner_id (uuid, fk users.id, indexed)
name (str 120)
dob (str YYYY-MM-DD, nullable)
created_at
```
Cascade-delete removes all events and schedules for that child.

**`custody_events`** — polymorphic (approach A from brainstorming).
```
id (str uuid, pk)
owner_id (uuid, fk users.id, indexed)
child_id (str uuid, fk custody_children.id CASCADE, indexed)
type (str enum)          -- see below
occurred_at (datetime tz, indexed)
notes (text, nullable)
location (str 255, nullable)
overnight (bool, default false)              -- pickups only
amount_cents (int, nullable)                 -- expense only
category (str enum, nullable)                -- expense only
call_connected (bool, nullable)              -- phone_call only
missed_source (str enum, nullable)           -- missed_visit only: auto|manual
schedule_id (str uuid, fk custody_schedules.id SET NULL, nullable)
created_at
```

`type` enum values: `pickup`, `dropoff`, `activity`, `expense`, `text_screenshot`, `medical`, `school`, `missed_visit`, `phone_call`, `note`. "Overnight" is a bool on pickup rows, not its own type.

`category` enum: `food`, `activity`, `clothing`, `school`, `medical`, `other`.

Indexes for the hot queries: `(owner_id, child_id, occurred_at DESC)` for the timeline; `(owner_id, type, occurred_at)` for "show me expenses this month".

**`custody_event_photos`** — mirrors `yardsailing_sale_photos` 1:1.
```
id (str uuid, pk)
event_id (str uuid, fk custody_events.id CASCADE, indexed)
position (int)
original_path (str 512)
thumb_path (str 512)
content_type (str 64)
created_at
```
Stored under `<UPLOADS_ROOT>/custody/<event_id>/`. Max 5 photos per event; 10MB each; jpeg/png/webp.

**`custody_schedules`** — recurrence rules.
```
id (str uuid, pk)
owner_id (uuid, fk users.id, indexed)
child_id (str uuid, fk custody_children.id CASCADE, indexed)
name (str 120)               -- e.g. "EOW Fri-Sun"
active (bool, default true)
start_date (str YYYY-MM-DD)  -- anchor for every-N-weeks math
interval_weeks (int, default 1)
weekdays (str)               -- comma-separated ints 0-6 (Mon=0 … Sun=6), e.g. "4,5,6"
pickup_time (str HH:MM)
dropoff_time (str HH:MM)
pickup_location (str 255, nullable)
created_at
```

**`custody_schedule_exceptions`** — overrides for individual dates.
```
id (str uuid, pk)
schedule_id (str uuid, fk custody_schedules.id CASCADE, indexed)
date (str YYYY-MM-DD)
kind (str enum: skip|override)
override_pickup_at (datetime tz, nullable)
override_dropoff_at (datetime tz, nullable)
```

### LLM tools

Handlers in `tools.py` mirror yardsailing's `(args, user, db)` signature. Skills in `plugin.json` group related tools.

- **`log_custody_event`** — covers pickup, dropoff, activity, note, medical, school, phone_call, text_screenshot (minus the photo, which comes from the component).
  - Args: `type` (required), `child_name`, `occurred_at?` (defaults to now), `notes?`, `location?`, `overnight?` (pickup only), `call_connected?` (phone_call only).
- **`log_expense`** — separated because of amount + category.
  - Args: `child_name`, `amount_usd`, `description`, `category?`, `occurred_at?`.
- **`log_missed_visit`** — manual entry when mother denied a visit.
  - Args: `child_name`, `expected_pickup_at`, `notes?`. Sets `missed_source="manual"`.
- **`query_custody_events`** — read-side for "how much did I spend this month?" / "when did I last see Mason?".
  - Args: `child_name?`, `type?`, `from_date?`, `to_date?`, `limit?` (default 20).
  - Returns `{events: [...], summary: {count, total_expense_usd, by_type, by_category}}` when a date range is given.
- **`show_custody_home`** — UI-only, mounts `CustodyHome` (mirrors yardsailing's `show_sale_form`).
- **`show_expense_form`** — UI-only, mounts `ExpenseForm` (for "I want to log an expense with a receipt").
- **`show_text_capture`** — UI-only, mounts `TextCaptureForm`.

**Child resolution:** server-side, case-insensitive match of `child_name` against `custody_children.name` scoped to `owner_id`. When the user has exactly one child and `child_name` is omitted, default to that child. On miss, return `{"error": "child_not_found", "known_children": [names]}` so the LLM asks for clarification.

### Backend routes

Prefix `/api/plugins/custody`. All auth via `get_current_user`; everything scoped by `owner_id = user.id`.

**Children**
- `GET /children` → list
- `POST /children` → `{name, dob?}` → create
- `PATCH /children/{id}` → partial update
- `DELETE /children/{id}` → 204 (cascades)

**Events**
- `GET /events?child_id=&type=&from=&to=&limit=&offset=` → paginated timeline (newest first, default 50)
- `POST /events` → `{type, child_id, occurred_at?, notes?, location?, overnight?, amount_cents?, category?, call_connected?, missed_source?, expected_pickup_at?}` → full event
- `PATCH /events/{id}` → partial update (notes/location/occurred_at/amount/category/overnight)
- `DELETE /events/{id}` → 204
- `POST /events/{id}/photos` → `UploadFile`; enforces 5/event cap, 10MB, allowed types
- `DELETE /events/{id}/photos/{photo_id}` → 204

**Schedules**
- `GET /schedules?child_id=` → list
- `POST /schedules` → create
- `PATCH /schedules/{id}` / `DELETE /schedules/{id}`
- `POST /schedules/{id}/exceptions` → `{date, kind, override_pickup_at?, override_dropoff_at?}`
- `DELETE /schedules/exceptions/{id}`

**Status & summary**
- `GET /status?child_id=` → `{state: "with_you"|"away"|"no_schedule", since?, next_pickup_at?, in_care_duration_seconds?, last_dropoff_at?}`. Computed per child from last pickup/dropoff and upcoming schedule.
- `GET /summary?child_id=&month=YYYY-MM` → `{visits_count, total_expense_cents, by_category: {food: cents, ...}, missed_visits_count}`.

**Missed-visit detection**
- `POST /schedules/refresh-missed?child_id=&up_to=YYYY-MM-DD` → idempotent re-compute; returns `{new_rows: int}`. Called by the mobile home screen on focus.

**Export**
- `GET /export?child_id=&from=&to=&format=pdf|csv` → file download (`Content-Disposition: attachment`).
  - **CSV** columns: `occurred_at, type, child, notes, location, amount_usd, category, photo_count, photo_urls`.
  - **PDF** generated with `reportlab` (add to `requirements.txt`). Grouped by day; each event shows timestamp, type label, core fields, and embedded thumbnails inline.

### Mobile components

Bundle path `bundle/custody.js`. Exports via `plugin.json`:

- **`CustodyHome`** — the plugin's home screen (per `plugin-home-screens` design).
  - Child selector strip (visible when 2+ children).
  - Status card (green "WITH YOU since X" when in care, neutral "Next pickup…" when not, prompt-to-create-schedule when no schedule).
  - Quick-action row: `+ Expense` / `+ Text screenshot` / `+ Activity` / `+ Note` / `⋯ More`.
  - Month strip: `6 visits · $214 spent · 1 missed`.
  - Scrollable timeline grouped by day, colored dot by type, tap → inline event detail sheet.
  - FAB for quick-add from deep scroll.
  - Header menu: `Export…` / `Schedules` / `Children`.
  - On mount: calls `POST /schedules/refresh-missed`; shows yellow banner if new missed rows appear.
- **`ExpenseForm`** — amount (numeric input), description, category chips, camera/photo picker (reuses yardsailing's photo pattern endpoint at `/api/plugins/custody/events/{id}/photos`).
- **`TextCaptureForm`** — take photo or pick from library + optional note.
- **`EventForm`** — generic for activity/note/medical/school/phone-call/missed-visit; field set varies by `type` prop.
- **`ScheduleForm`** — name, child, interval_weeks, weekday toggle row, pickup/dropoff time pickers, optional pickup_location.
- **`ScheduleListScreen`**, **`ChildrenScreen`**, **`ExportSheet`** — dedicated inline screens reachable from the header menu.

All components consume the existing bridge (`api`, `openComponent`, `closeComponent`, `toast`). Uses the `openComponent` verb introduced by `plugin-home-screens` to mount sub-forms.

### Schedule & missed-visit detection

Lives in `schedules.py`, fully deterministic and test-isolated.

**Expected pickups** for a schedule over `[from_date, up_to_date]`:
1. Walk each date in range.
2. Skip if `(date - start_date).days // 7 % interval_weeks != 0` (handles EOW).
3. Skip if weekday not in `weekdays`.
4. Apply `custody_schedule_exceptions` for that date: `skip` removes the occurrence; `override` replaces expected pickup/dropoff datetimes.
5. Expected pickup datetime = `date` + `pickup_time` (server local → stored UTC for v1; per-user tz deferred).

**`refresh_missed(child_id, up_to)`**:
- For each active schedule on that child:
  - Generate expected pickups from `start_date` up to `up_to`.
  - For each expected pickup at `E`: look for a `pickup` event in `[E - 2h, E + 2h]`. If found → skip.
  - Look for an existing `missed_visit` row with matching `schedule_id` and `occurred_at` in `[E - 4h, E + 4h]`. If found → skip.
  - Otherwise insert `missed_visit` row with `occurred_at = E`, `missed_source = "auto"`, `schedule_id` set, `notes = "Auto-flagged: no pickup within 2h of scheduled {HH:MM}"`.
- Return count of new rows.

User can `DELETE /events/{id}` to clear false positives. Manual `log_missed_visit` blocks auto re-flagging of the same date via the schedule_id + 4h window check.

### File layout

```
backend/app/plugins/custody/
  __init__.py              register() → PluginRegistration
  plugin.json              manifest: skills, home, components.exports
  models.py                Child, CustodyEvent, EventPhoto, Schedule, ScheduleException
  routes.py                FastAPI router
  tools.py                 LLM tool defs + handlers
  services.py              CRUD: children, events, schedules
  schedules.py             recurrence + refresh_missed
  photos.py                thin binding to app/plugins/core/photos.py
  export.py                CSV + PDF generation
  help.md                  user docs for the Help screen
  build.mjs                esbuild config (copy from yardsailing)
  package.json             bundle deps
  components/
    CustodyHome.tsx
    ExpenseForm.tsx
    TextCaptureForm.tsx
    EventForm.tsx
    ScheduleForm.tsx
    ScheduleListScreen.tsx
    ChildrenScreen.tsx
    ExportSheet.tsx
    eventDetail.tsx
  bundle/                  built output
```

### Shared photo helper refactor

`backend/app/plugins/yardsailing/photos.py` is ~90% generic upload + thumbnail + validation. Extract into `backend/app/plugins/core/photos.py`:

- Module constants: `MAX_BYTES`, `ALLOWED_TYPES`, `THUMB_MAX_DIM`, `_ext_for`.
- `generate_thumbnail(src_path, dst_path)` unchanged.
- `save_upload(root: Path, sub_path: str, upload: UploadFile) -> SavedPhoto` returning a value object with `original_path`, `thumb_path`, `content_type`.
- `delete_files(root: Path, original_path: str, thumb_path: str)`.

Plugin-specific glue stays in each plugin's `photos.py`:
- Yardsailing: binds `SalePhoto`, uses `sales/<sale_id>/`, enforces `MAX_PHOTOS_PER_SALE = 5`.
- Custody: binds `EventPhoto`, uses `custody/<event_id>/`, same 5/event cap.

This is the targeted code improvement the brainstorming skill calls out — we're touching photo code for custody anyway, and there's no reason to copy-paste yardsailing's 108 lines.

## Loading & migration

- No explicit registration list: `InternalPluginLoader` walks `backend/app/plugins/` at startup and imports every package with a `register()` function. Dropping the `custody/` directory in is sufficient.
- Tables are created by `Base.metadata.create_all` when `models.py` is imported at startup — same pattern yardsailing uses. No Alembic migration needed for the initial ship.
- `reportlab` added to `backend/requirements.txt` (pure Python, no system deps).

## Test plan

Pytest + httpx AsyncClient, matching yardsailing's style:

- **`test_models.py`** — create child, create one event of each type, cascade-delete child removes events + photos + schedules.
- **`test_routes.py`** — CRUD round-trips for children/events/schedules; owner scoping (user A cannot read/write user B's data); photo upload enforces 5-per-event cap and type/size limits; pagination correctness.
- **`test_schedules.py`** — recurrence math: weekly, EOW with two-week offsets, weekday filters, skip exception removes an occurrence, override exception replaces times, boundary dates at year/month edges.
- **`test_missed_visits.py`** — pickup inside 2h window suppresses auto-flag; outside window triggers auto-flag; duplicate calls to `refresh_missed` are idempotent; manual `missed_visit` suppresses auto-flag for the same date.
- **`test_tools.py`** — LLM handlers: single-child default for `child_name`, case-insensitive name match, `child_not_found` error shape, `occurred_at` default to now, expense amount conversion (USD → cents).
- **`test_export.py`** — CSV row/column shape for a sample range; PDF file is non-empty and contains expected date headers; date range filter excludes out-of-range events.
- **`test_photos_shared.py`** — the extracted `app/plugins/core/photos.py` helpers: thumbnail generated, invalid content-type rejected, over-limit file rejected.

Mobile: tsc clean on the plugin bundle build; manual smoke test of each component path during plan execution.

## Migration / Compat

- No existing `custody_*` tables, so no data migration.
- Yardsailing photo code is refactored in place; its `SalePhoto` model stays unchanged and the external API shape is identical. Existing yardsailing tests should pass unmodified.

## Non-goals

- Reminders or notifications of any kind.
- Co-parent accounting / splits / payments.
- Court-specific legal templates (the PDF is a plain chronological record — lawyer formats the submission).
- Any integration with external calendars (Google/Apple).
- Bulk import from other custody-tracking apps.

## Open questions

- **Server vs per-user timezones.** V1 uses server local time for computing expected pickup datetimes. If users in different zones install the plugin, the schedule math will drift. Flag as a known limitation; add a user-level tz column in a later phase.
- **Photo cap.** 5 per event matches yardsailing; may be too few for text-screenshot chains. Keep 5 for v1, revisit if feedback says otherwise.
- **Deletion policy for missed-visit auto-flags.** V1 deletes the row on user dismiss; alternative is a `status` column (`auto|confirmed|dismissed`). Go with delete for v1 to keep the schema small.
