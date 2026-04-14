# Yardsailing Route Planner — Design Spec

**Date:** 2026-04-14
**Status:** Approved (pending user review of written spec)
**Plugin:** yardsailing (internal)

## Goal

Let a user plan an ordered, time-aware route through multiple yard sales, then hand off to Apple/Google Maps for turn-by-turn driving. Exposed as both a UI action on the filtered sale list and an LLM-callable tool.

## User Flow

### UI path
1. User filters the sale list with existing filters (radius, tags, time window).
2. User enters select mode and ticks sales (≥2) from the filtered list.
3. "Plan Route (N)" button plans and renders a route view.
4. Route view shows ordered stops with per-stop ETA, in-window/late flag, total distance and drive time.
5. "Open in Maps" hands off waypoints to the platform's native map app.

### Chat path
- LLM calls `plan_route` tool with either explicit `sale_ids` or a filter matching `find_yard_sales` shape.
- Backend returns a structured route.
- `ChatScreen` renders it via the same `<RouteCard />` component used in the UI path.

## Architecture

### Backend

**New module:** `backend/app/plugins/yardsailing/routing.py`

Public entry point:

```python
async def plan_route(
    sale_ids: list[int],
    start: LatLng,
    arrive_by: datetime | None = None,
    db: AsyncSession = ...,
) -> Route
```

Returns a `Route` with:
- `stops: list[RouteStop]` (ordered; each has sale, ETA, in_window flag)
- `total_distance_miles: float`
- `total_duration_minutes: float`
- `excluded: list[ExcludedSale]` (empty for soft-mode; reserved for future strict mode)

**Algorithm.** Cap at 10 stops. Brute-force permutations over Haversine distances — worst case 10! = 3.6M evaluations, runs in well under a second. No external routing API; Apple/Google Maps handles real driving directions on handoff. Haversine with a configurable average speed constant (default 35 mph) is sufficient for ordering at yard-sale scale.

**Time-window handling (soft).**
- Compute cumulative ETA per stop from start location.
- Flag stops where ETA exceeds the sale's end time (`in_window=False`); include them in the route anyway.
- Tie-break ordering to prefer sales closing earliest.

**Tool registration.** `plan_route` added to `backend/app/plugins/yardsailing/tools.py` alongside `find_yard_sales`. Input schema accepts either `sale_ids: list[int]` or `filter` (same shape as `find_yard_sales`), plus optional `start_location: {lat, lng}`. If `start_location` omitted, the tool expects the caller to supply it (mobile always does; chat path relies on stored user location).

**No new tables.** Routes are ephemeral — computed on demand, never persisted. Saved/named routes are explicitly out of scope.

### Mobile

**New components** under `mobile/src/plugins/yardsailing/`:

- `RouteCard.tsx` — ordered stop list; per-stop ETA badge (green = in window, amber = late); header with total distance and drive time; "Open in Maps" button. Used by both UI and chat render paths.
- `PlanRouteButton.tsx` — floating "Plan Route (N)" button; visible in the filtered sale list when ≥2 sales are selected.

**Sale list changes.** Add multi-select mode to the existing filtered list. Entered via a "Select" toggle; tapping a list item toggles its inclusion in the route set. A count badge tracks selected sales; cap of 10 enforced with a tooltip on the 11th tap.

**Handoff.**
- **iOS:** `http://maps.apple.com/?daddr=lat1,lng1&daddr=lat2,lng2&...` (chained `daddr` parameters).
- **Android:** `https://www.google.com/maps/dir/?api=1&waypoints=lat1,lng1|lat2,lng2|...` (browser handoff; `google.navigation:` intent supports only one destination).
- Platform detection via `Platform.OS`.

**Chat rendering.** Extend the existing tool-result render switch in `ChatScreen` (which already handles `find_yard_sales`) to render `plan_route` results with `<RouteCard />`.

## Testing

### Backend (pytest)

- `test_routing_orders_by_nearest_neighbor` — 3 stops, assert order matches optimal.
- `test_routing_respects_start_location` — different starts yield different first stops.
- `test_routing_flags_late_arrival` — sale ends before reachable ETA → `in_window=False`, still included.
- `test_routing_rejects_over_cap` — >10 stops returns 400.
- `test_plan_route_tool_via_filter` — tool handler path, filter-based selection.
- `test_plan_route_tool_via_ids` — tool handler path, explicit ID selection.

### Mobile

No unit tests for route math (lives on backend). Manual QA checklist:
- Select 2 sales, plan route, open in Maps (iOS + Android).
- Select 10 sales (hit the cap).
- Try to tick an 11th (tooltip shown).
- Mix in-window and out-of-window sales; verify amber badges.
- Chat path: "plan a route of today's sales within 3 miles" → route card renders, Open in Maps works.

## Out of Scope

- Saved or named routes (no persistence).
- Live re-routing while driving (Maps app's job).
- Traffic-aware ETAs (Haversine + constant speed is fine).
- Strict-mode window filtering (soft-only for v1).
- Multi-day routes.
- In-app turn-by-turn navigation.

## Open Questions

- **Start location for the chat path.** Mobile UI always supplies GPS. The LLM does not have access to device location in-prompt. Options: (a) mobile injects current location into every chat request as context; (b) `plan_route` returns an error if called without `start_location` and the LLM asks the user; (c) store user's home address and fall back to it. To be resolved in the implementation plan.
