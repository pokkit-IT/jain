# Yardsailing Pin-Drop Sightings — Design Spec

**Date:** 2026-04-15
**Status:** Draft
**Plugin:** yardsailing (internal)

## Goal

Let yard-sale hunters drop a pin on the map when they come across a sale that isn't listed. A single drop shows as **Unconfirmed**; when a second user drops a pin within 50 m of the first, it promotes to **Confirmed**. Sightings render on the map like hosted sales but with visual distinction, and sightings are uneditable once dropped.

## Scope

- **New pin type** via an extra `source` field on `Sale` plus a `confirmations` count.
  - `source="host"` → existing hosted sales. Unchanged.
  - `source="sighting"` → user-dropped pin.
- **Dedup radius:** 50 m. If a new drop falls within 50 m of an existing sighting (on the same calendar day), it bumps that sighting's `confirmations` and is NOT a new row.
- **Promotion:** `confirmations >= 2` renders as "Confirmed"; `confirmations == 1` renders as "Unconfirmed".
- **No edits.** Sighting rows are immutable after creation. No title updates, no photo uploads, no tag edits, no owner-only endpoints.
- **No title.** Leave it as `"Unconfirmed sale"` placeholder (set server-side so clients don't have to).
- **Address = lat/lng** rendered as `"<lat>, <lng>"` at a fixed 5-decimal precision. No reverse geocoding.
- **Time defaults** (server-computed at drop time, in the user's reported local clock):
  - `start_date = end_date = today`
  - `start_time = now` (rounded to the minute)
  - `end_time = min(now + 2h, 17:00)`
- **Drop window:** if now ≥ 17:00, reject the drop (409 `drop_window_closed`). The UI should disable the drop control past 17:00.
- **Unconfirmed expiry:** 2 hours after creation, unconfirmed sightings stop rendering on the map. Confirmed sightings live until their `end_time` like any other sale. No background job needed — the public listing query filters them out.
- **Ownership:** sightings carry `owner_id` of the dropper so future moderation can see who dropped; no other rights. (No delete for v1; they just age out.)
- **Groups/photos/tags:** sightings never have any of these.

## User Flow

### Drop

1. Long-press on the Map. A confirmation sheet appears: *"Drop unconfirmed yard sale here?"* with the pin coords.
2. User confirms → `POST /sightings` with `{lat, lng}`. Client also sends current local HH:MM (server validates against UTC but accepts a client-supplied `now_hhmm` for the 17:00 gate so the user's timezone is honored).
3. Backend either (a) creates a new `Sale` row with `source="sighting", confirmations=1`, or (b) if another sighting exists within 50 m on today's date, bumps that row's `confirmations` and returns it.
4. Map refreshes; pin appears (or the existing pin's label flips to "Confirmed").

### Tap

Tapping a sighting pin shows a minimal popup (not the full `SaleDetailsModal`):
- Status badge: **Unconfirmed** or **Confirmed**
- Address line: `"<lat>, <lng>"`
- Hours: `start_time – end_time`
- Directions button (same deeplink path as hosted sales)

No edit, no photos, no tags, no "delete."

## Architecture

### Backend

**Schema change** — `Sale` model gains two columns:

| Column          | Type        | Default       | Notes                                     |
|-----------------|-------------|---------------|-------------------------------------------|
| `source`        | `str(16)`   | `"host"`      | One of `"host"`, `"sighting"`.            |
| `confirmations` | `int`       | `1`           | Only meaningful when `source="sighting"`. |

Dev migration in `database._apply_dev_migrations` adds both columns idempotently on SQLite.

**Helper** — `haversine_meters(lat1, lng1, lat2, lng2) -> float` in `routing.py` (or a new `geo.py`). Used both by the dedup check and future route planning.

**Service** — `sightings.py`:
- `async def drop_sighting(db, user, lat, lng, now_dt) -> Sale` — validates `now_dt.hour < 17`, searches existing sightings with `source="sighting" AND start_date=today` and computes distance; if any within 50 m, increments `confirmations` on the nearest and returns it; otherwise creates a fresh `Sale` row with the computed defaults.
- `DROP_CUTOFF_HOUR = 17`
- `UNCONFIRMED_TTL_MINUTES = 120`

**Query filters** — `list_recent_sales` gains a condition that drops expired unconfirmed sightings:
```
WHERE NOT (source='sighting' AND confirmations=1
           AND created_at < now() - interval '2 hours')
```
(SQL written for SQLite: `datetime(created_at) < datetime('now', '-120 minutes')`.)

**Endpoint** — `POST /api/plugins/yardsailing/sightings`:
- Body: `{lat: float, lng: float, now_hhmm: str}` (client-supplied wall clock, formatted `HH:MM`, used for the 17:00 gate).
- Auth required.
- Responses:
  - `201` with the created or bumped sighting (same `SaleResponse` shape plus `source` + `confirmations`).
  - `409` `{"detail": "drop_window_closed"}` if `now_hhmm >= "17:00"`.
  - `422` on coord validation.

**Serialization** — `SaleResponse` adds `source: str` and `confirmations: int` so the map knows to style sighting pins and show the "Unconfirmed"/"Confirmed" badge.

**Skill / tool change** — not in scope; LLM doesn't drop pins.

### Frontend (mobile app)

- `Sale` type gains `source?: "host" | "sighting"` and `confirmations?: number`.
- `Map.tsx` — long-press handler captures the tap coords, opens a confirmation Modal, then calls `postSighting(lat, lng, nowHHMM)`. Client-side 17:00 guard hides the control.
- Pin rendering — sighting pins get a distinct color (orange for unconfirmed, green for confirmed) vs. the default blue for hosted sales.
- New `SightingPopup` component (tiny; not `SaleDetailsModal`) with status badge, coords, hours, and Directions button.
- `yardsailing.ts` API — `postSighting(lat, lng, nowHHMM)` and include `source`/`confirmations` in fetched Sales.

## Validation & Edge Cases

- `0 < lat`, `-180 <= lng <= 180` — reject 422.
- Dedup search is scoped to `start_date = today` so a sighting from yesterday doesn't absorb today's drops.
- Server records `now_dt = datetime.now(tz=...) ` but trusts client-supplied `now_hhmm` for the cutoff gate (server time may be UTC; user's local clock is what matters for "5 PM").
- Rapid-fire double-taps by the same user at the same spot: same dedup rule applies — the user's second drop still counts as a confirmation (tests pin this; we may later decide same-user repeats don't count, but v1 trusts the drops).

## Test Plan

- Backend unit: dedup within 50 m vs. 51 m; today-scoped dedup; 17:00 cutoff; `end_time = min(now+2h, 17:00)`; unconfirmed expiry filter in `list_recent_sales`.
- Backend route: 201 on fresh drop, 201 on dedup bump (with `confirmations == 2`), 409 on post-cutoff, 401 on anon.
- Frontend: tsc clean; manual smoke through long-press → confirm → pin appears; second drop 30 m away bumps to Confirmed.

## Out of Scope

- Moderation / reporting bogus sightings.
- Auto-converting a confirmed sighting into an editable hosted sale.
- Photo uploads on sightings.
- Push notifications when a nearby sighting appears.
- Reverse geocoding the pin to a street address.
