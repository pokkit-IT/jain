# Yardsailing Pin-Drop — Implementation Plan

**Date:** 2026-04-15
**Spec:** `docs/superpowers/specs/2026-04-15-yardsailing-pin-drop-design.md`
**Branch:** `feature/yardsailing-pin-drop`

## Phases

### Phase 1 — Backend schema

1. Add `source` (default `"host"`) and `confirmations` (default `1`) columns to `Sale`.
2. Extend `database._apply_dev_migrations` so SQLite dev DBs get both columns added idempotently.
3. Unit tests: default values for existing rows; column presence; check that new Sales default to `source="host"`.

Exit: `pytest backend/tests/plugins/yardsailing/test_models.py` green.

### Phase 2 — Sightings service

1. New `sightings.py` with `drop_sighting(db, user, lat, lng, now_hhmm) -> Sale`.
2. `haversine_meters` helper (either a new `geo.py` or appended to `routing.py`).
3. Dedup search: today-scoped, `source="sighting"`, distance ≤ 50 m, nearest wins.
4. Compute end_time = `min(now+2h, 17:00)`.
5. 17:00 cutoff raises a typed `DropWindowClosed` exception.
6. Tests: fresh drop path, dedup bump path, 51 m no-merge, cross-day no-merge, 17:00 cutoff, end_time clamp.

Exit: `pytest backend/tests/plugins/yardsailing/test_sightings_module.py` green.

### Phase 3 — Listings filter + endpoint

1. Update `list_recent_sales` so unconfirmed sightings older than 120 minutes are filtered out at the SQL level.
2. Add `POST /api/plugins/yardsailing/sightings` wired to `drop_sighting`. 201 on success, 409 on `DropWindowClosed`, 422 on coord validation, 401 on anon.
3. Include `source` and `confirmations` in `SaleResponse`.
4. Route tests.

Exit: `pytest backend/tests/plugins/yardsailing/test_routes.py` and `test_sightings_routes.py` green.

### Phase 4 — Mobile types + API client

1. Extend `Sale` type with `source?: "host" | "sighting"` and `confirmations?: number`.
2. Add `postSighting(lat, lng, nowHHMM)` to `api/yardsailing.ts`.

Exit: tsc clean.

### Phase 5 — Map long-press + drop modal

1. Add long-press handler on `Map.tsx` (and `Map.web.tsx` fallback / no-op for web).
2. Confirmation modal: shows coords, "Drop unconfirmed yard sale here?", confirm + cancel.
3. After successful drop, refresh the map.
4. Client-side guard: if now ≥ 17:00 local, hide/disable the feature with a toast explanation.

Exit: Manual smoke — long-press on iOS simulator, confirm, pin appears with orange color and "Unconfirmed" badge.

### Phase 6 — Sighting pin styling + tap popup

1. Pin color / icon differs by `source` and `confirmations`:
   - `host` → blue
   - `sighting, confirmations=1` → orange
   - `sighting, confirmations>=2` → green
2. New `SightingPopup` component (smaller than `SaleDetailsModal`): status badge, coords, hours, Directions button.
3. Tap routing: hosted sales open `SaleDetailsModal`; sightings open `SightingPopup`.

Exit: Manual smoke — tap any sighting shows the popup with the right badge.

### Phase 7 — Docs & ship

1. Update `help.md` with a "Spot an unlisted sale?" section.
2. Rebuild plugin bundle (note: pin-drop logic lives in the mobile app, not the plugin bundle, but help.md is served by the plugin).
3. PR against main.

## Risks / Notes

- **Client clock trust.** We accept `now_hhmm` from the client for the 17:00 gate because server may be UTC. This is intentional for v1; could be abused (someone sends `"12:00"` at 9 PM). Acceptable for v1.
- **Dedup race.** Two users drop within the same second 10 m apart — both queries see zero existing sightings, both insert. Tolerable: there'll be two rows instead of one merged; a future cleanup job or `FOR UPDATE` lock could fix it. Not blocking.
- **Expiry filter cost.** Adding a time-based predicate to `list_recent_sales` is cheap at our scale; no index needed yet.
- **Map web fallback.** `Map.web.tsx` uses a simpler map; long-press may need a custom click handler or could be skipped entirely on web in v1.

## Deliberate non-goals

- No conversion of confirmed sightings into editable hosted sales.
- No moderation / report-abuse flow.
- No photo uploads or tags on sightings.
- No push notifications.
- No reverse geocoding — address is just the lat/lng.
