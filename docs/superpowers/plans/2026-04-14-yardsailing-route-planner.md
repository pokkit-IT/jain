# Yardsailing Route Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ordered, time-aware multi-stop route planning for selected yard sales, exposed as both an LLM tool and a mobile UI action, with Apple/Google Maps handoff for turn-by-turn driving.

**Architecture:** New pure-Python `routing` module inside the yardsailing internal plugin computes routes via brute-force TSP over Haversine distances (capped at 10 stops). A `plan_route` LLM tool and a `POST /api/plugins/yardsailing/plan_route` HTTP endpoint both call into it. Mobile adds a multi-select mode to the existing in-chat sale list (`DataCard`) with displayHint `"map"`, a `PlanRouteButton` that calls the HTTP endpoint, and a new `RouteCard` render path for displayHint `"route"` results. Platform-aware handoff builds an Apple Maps or Google Maps URL.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.0 async, pydantic v2, pytest, React Native + Expo, TypeScript.

---

## Pre-flight notes

1. The spec's "filtered sale list" is, in the current app, the in-chat `DataCard` that renders `find_yard_sales` tool results with `displayHint="map"`. There is no standalone filtered-list screen; multi-select is added to the in-chat card.
2. A Haversine helper already exists at `backend/app/plugins/yardsailing/tools.py:20` (`_haversine_miles`). Task 1 moves it to the new `routing.py` module to avoid duplication. `tools.py` imports it from there.
3. The tool executor dispatches internal tool calls via the plugin loader and `ToolDef.handler` (see existing `find_yard_sales` in `tools.py:104`). `plan_route` registers the same way.
4. Open question from spec (start location for chat path): resolved in Task 12 — mobile injects location via the HTTP endpoint; the LLM-callable tool requires `start_location` in args and returns a structured error if missing so the LLM can ask the user.

---

## Stage 1: Backend routing module

### Task 1: Create `routing.py` with types and shared Haversine helper

**Files:**
- Create: `backend/app/plugins/yardsailing/routing.py`
- Modify: `backend/app/plugins/yardsailing/tools.py` (import haversine from routing)
- Create: `backend/tests/plugins/yardsailing/test_routing.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/plugins/yardsailing/test_routing.py`:

```python
from app.plugins.yardsailing.routing import (
    LatLng,
    RouteStop,
    Route,
    haversine_miles,
)


def test_haversine_zero_distance():
    assert haversine_miles(40.0, -80.0, 40.0, -80.0) == 0.0


def test_haversine_known_distance():
    # New York City to Philadelphia is ~80 miles
    d = haversine_miles(40.7128, -74.0060, 39.9526, -75.1652)
    assert 75 < d < 90


def test_types_instantiate():
    s = LatLng(lat=40.0, lng=-80.0)
    assert s.lat == 40.0
    stop = RouteStop(sale_id=1, eta_minutes=10.0, in_window=True)
    assert stop.sale_id == 1
    r = Route(stops=[stop], total_distance_miles=5.0, total_duration_minutes=10.0, excluded=[])
    assert r.stops == [stop]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/plugins/yardsailing/test_routing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.plugins.yardsailing.routing'`.

- [ ] **Step 3: Create the module**

Create `backend/app/plugins/yardsailing/routing.py`:

```python
"""Route planning for the yardsailing internal plugin.

Pure functions over Haversine distances. Brute-force TSP capped at
MAX_STOPS=10. Callers: the `plan_route` tool handler and the
`/api/plugins/yardsailing/plan_route` HTTP endpoint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import permutations

MAX_STOPS = 10
AVG_SPEED_MPH = 35.0
_EARTH_RADIUS_MI = 3958.7613


@dataclass
class LatLng:
    lat: float
    lng: float


@dataclass
class RouteStop:
    sale_id: int
    eta_minutes: float
    in_window: bool


@dataclass
class ExcludedSale:
    sale_id: int
    reason: str


@dataclass
class Route:
    stops: list[RouteStop]
    total_distance_miles: float
    total_duration_minutes: float
    excluded: list[ExcludedSale] = field(default_factory=list)


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_MI * math.asin(math.sqrt(a))
```

- [ ] **Step 4: Switch `tools.py` to import from routing**

Edit `backend/app/plugins/yardsailing/tools.py`. Replace the local `_haversine_miles` definition (lines ~18–25) with an import:

```python
from .routing import haversine_miles as _haversine_miles
```

Remove the `_EARTH_RADIUS_MI` constant and the `_haversine_miles` function body. Keep the `import math` line only if used elsewhere; otherwise remove.

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/plugins/yardsailing/ -v`
Expected: all new tests PASS; existing `test_tools.py` tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/plugins/yardsailing/routing.py backend/app/plugins/yardsailing/tools.py backend/tests/plugins/yardsailing/test_routing.py
git commit -m "feat(yardsailing): routing module scaffold with shared haversine"
```

---

### Task 2: Implement `plan_route` with brute-force TSP ordering

**Files:**
- Modify: `backend/app/plugins/yardsailing/routing.py`
- Modify: `backend/tests/plugins/yardsailing/test_routing.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_routing.py`:

```python
import pytest
from datetime import datetime

from app.plugins.yardsailing.routing import (
    MAX_STOPS,
    LatLng,
    SaleInput,
    plan_route,
)


def _sale(sid, lat, lng, end=None):
    return SaleInput(id=sid, lat=lat, lng=lng, end_datetime=end)


def test_plan_route_orders_by_nearest_neighbor_when_clear():
    # Start at origin. Three sales on a line: (0,1) (0,2) (0,5).
    # Optimal order is 1, 2, 5 in that order.
    start = LatLng(lat=0.0, lng=0.0)
    sales = [
        _sale(5, 0.0, 0.05),   # furthest
        _sale(2, 0.0, 0.02),
        _sale(1, 0.0, 0.01),   # closest
    ]
    route = plan_route(start, sales, now=datetime(2026, 4, 14, 8, 0, 0))
    assert [s.sale_id for s in route.stops] == [1, 2, 5]


def test_plan_route_start_location_matters():
    # Two sales. Start near A → A first. Start near B → B first.
    sale_a = _sale(1, 40.0, -80.0)
    sale_b = _sale(2, 41.0, -80.0)
    start_near_a = LatLng(lat=40.0, lng=-80.01)
    start_near_b = LatLng(lat=41.0, lng=-80.01)
    r1 = plan_route(start_near_a, [sale_a, sale_b], now=datetime(2026, 4, 14, 8, 0, 0))
    r2 = plan_route(start_near_b, [sale_a, sale_b], now=datetime(2026, 4, 14, 8, 0, 0))
    assert r1.stops[0].sale_id == 1
    assert r2.stops[0].sale_id == 2


def test_plan_route_rejects_over_cap():
    start = LatLng(lat=0.0, lng=0.0)
    sales = [_sale(i, 0.0, 0.01 * i) for i in range(1, MAX_STOPS + 2)]
    with pytest.raises(ValueError, match="too many stops"):
        plan_route(start, sales, now=datetime(2026, 4, 14, 8, 0, 0))


def test_plan_route_flags_late_arrival():
    # One sale 50 miles away, ends in 30 minutes. Can't get there in time at 35mph.
    start = LatLng(lat=0.0, lng=0.0)
    far = _sale(
        1,
        lat=0.0,
        lng=50.0 / 69.0,  # ~50 miles east at the equator (1 deg lng ~= 69 mi)
        end=datetime(2026, 4, 14, 8, 30, 0),
    )
    route = plan_route(start, [far], now=datetime(2026, 4, 14, 8, 0, 0))
    assert len(route.stops) == 1
    assert route.stops[0].sale_id == 1
    assert route.stops[0].in_window is False


def test_plan_route_returns_totals():
    start = LatLng(lat=0.0, lng=0.0)
    sales = [_sale(1, 0.0, 0.1), _sale(2, 0.0, 0.2)]
    route = plan_route(start, sales, now=datetime(2026, 4, 14, 8, 0, 0))
    assert route.total_distance_miles > 0
    assert route.total_duration_minutes > 0
    # Distances sum to at least leg1 + leg2
    assert route.total_distance_miles >= 0.1  # sanity
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/plugins/yardsailing/test_routing.py -v`
Expected: FAIL — `SaleInput` and `plan_route` not yet defined.

- [ ] **Step 3: Implement `SaleInput` and `plan_route`**

Append to `backend/app/plugins/yardsailing/routing.py`:

```python
@dataclass
class SaleInput:
    """Minimal sale shape needed for routing. end_datetime is the
    datetime the sale closes; None means no window check."""
    id: int
    lat: float
    lng: float
    end_datetime: datetime | None = None


def _leg_duration_minutes(miles: float) -> float:
    return (miles / AVG_SPEED_MPH) * 60.0


def plan_route(
    start: LatLng,
    sales: list[SaleInput],
    now: datetime,
) -> Route:
    """Order the given sales into the shortest round-trip-free route
    starting from `start`. Cap of MAX_STOPS enforced. Each stop gets an
    ETA and an in_window flag (soft mode: late stops are still
    included)."""
    if len(sales) > MAX_STOPS:
        raise ValueError(f"too many stops (max {MAX_STOPS})")
    if not sales:
        return Route(stops=[], total_distance_miles=0.0, total_duration_minutes=0.0)

    # Brute-force: try every permutation, pick the one with minimum
    # total distance. 10! = 3.6M — still under a second in pure Python
    # with Haversine math.
    best_order: list[SaleInput] | None = None
    best_distance = float("inf")
    for perm in permutations(sales):
        total = haversine_miles(start.lat, start.lng, perm[0].lat, perm[0].lng)
        for i in range(len(perm) - 1):
            total += haversine_miles(
                perm[i].lat, perm[i].lng, perm[i + 1].lat, perm[i + 1].lng
            )
        if total < best_distance:
            best_distance = total
            best_order = list(perm)

    assert best_order is not None
    stops: list[RouteStop] = []
    cumulative_miles = 0.0
    prev_lat, prev_lng = start.lat, start.lng
    for s in best_order:
        cumulative_miles += haversine_miles(prev_lat, prev_lng, s.lat, s.lng)
        eta_min = _leg_duration_minutes(cumulative_miles)
        in_window = True
        if s.end_datetime is not None:
            arrival = now + timedelta(minutes=eta_min)
            in_window = arrival <= s.end_datetime
        stops.append(RouteStop(sale_id=s.id, eta_minutes=eta_min, in_window=in_window))
        prev_lat, prev_lng = s.lat, s.lng

    return Route(
        stops=stops,
        total_distance_miles=best_distance,
        total_duration_minutes=_leg_duration_minutes(best_distance),
    )
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/plugins/yardsailing/test_routing.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/routing.py backend/tests/plugins/yardsailing/test_routing.py
git commit -m "feat(yardsailing): plan_route with brute-force TSP and in-window flagging"
```

---

## Stage 2: Tool and endpoint integration

### Task 3: Add `plan_route` LLM tool with `sale_ids` path

**Files:**
- Modify: `backend/app/plugins/yardsailing/tools.py`
- Create: `backend/tests/plugins/yardsailing/test_plan_route_tool.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/plugins/yardsailing/test_plan_route_tool.py`:

```python
import pytest
from datetime import date, time

from app.plugins.yardsailing.services import CreateSaleInput, create_sale
from app.plugins.yardsailing.tools import plan_route_handler


@pytest.mark.asyncio
async def test_plan_route_handler_orders_two_sales(db_session, user_fixture):
    # Create two sales with known coordinates (geocoding is mocked in conftest)
    await create_sale(db_session, user_fixture, CreateSaleInput(
        title="Near", address="100 Main St", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
    ))
    await create_sale(db_session, user_fixture, CreateSaleInput(
        title="Far", address="200 Main St", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
    ))
    # Query DB to get the IDs
    from app.plugins.yardsailing.services import list_recent_sales
    all_sales = await list_recent_sales(db_session, limit=10)
    ids = [s.id for s in all_sales]

    result = await plan_route_handler(
        {
            "sale_ids": ids,
            "start_location": {"lat": 0.0, "lng": 0.0},
        },
        user=user_fixture,
        db=db_session,
    )
    assert "route" in result
    assert result["route"]["stops"]
    assert len(result["route"]["stops"]) == 2


@pytest.mark.asyncio
async def test_plan_route_handler_missing_start_location(db_session, user_fixture):
    result = await plan_route_handler(
        {"sale_ids": [1]},
        user=user_fixture,
        db=db_session,
    )
    assert result.get("error") == "start_location_required"
```

(The `db_session` and `user_fixture` fixtures already exist in `backend/tests/plugins/yardsailing/conftest.py`.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/plugins/yardsailing/test_plan_route_tool.py -v`
Expected: FAIL — `plan_route_handler` not defined.

- [ ] **Step 3: Add `plan_route_handler` and register the tool**

Edit `backend/app/plugins/yardsailing/tools.py`. Add imports near the top:

```python
from datetime import datetime, date as date_cls, time as time_cls

from .routing import LatLng, SaleInput, plan_route, MAX_STOPS
```

Append a handler and update the `TOOLS` list:

```python
async def plan_route_handler(args, user=None, db=None):
    """Plan an ordered route through selected yard sales."""
    start_raw = args.get("start_location")
    if not start_raw or "lat" not in start_raw or "lng" not in start_raw:
        return {"error": "start_location_required"}
    start = LatLng(lat=float(start_raw["lat"]), lng=float(start_raw["lng"]))

    sale_ids = args.get("sale_ids") or []
    if not sale_ids:
        return {"error": "no_sales_provided"}
    if len(sale_ids) > MAX_STOPS:
        return {"error": "too_many_stops", "max": MAX_STOPS}

    from .models import Sale
    from sqlalchemy import select
    res = await db.execute(select(Sale).where(Sale.id.in_(sale_ids)))
    sales = res.scalars().all()
    if not sales:
        return {"error": "no_sales_found"}

    inputs: list[SaleInput] = []
    sale_lookup: dict[int, Sale] = {}
    for s in sales:
        if s.lat is None or s.lng is None:
            continue
        end_dt = None
        if s.end_date and s.end_time:
            try:
                end_dt = datetime.combine(
                    date_cls.fromisoformat(s.end_date),
                    time_cls.fromisoformat(s.end_time),
                )
            except ValueError:
                end_dt = None
        inputs.append(SaleInput(id=s.id, lat=s.lat, lng=s.lng, end_datetime=end_dt))
        sale_lookup[s.id] = s

    route = plan_route(start, inputs, now=datetime.utcnow())
    return {
        "route": {
            "stops": [
                {
                    "sale_id": st.sale_id,
                    "eta_minutes": round(st.eta_minutes, 1),
                    "in_window": st.in_window,
                    "title": sale_lookup[st.sale_id].title,
                    "address": sale_lookup[st.sale_id].address,
                    "lat": sale_lookup[st.sale_id].lat,
                    "lng": sale_lookup[st.sale_id].lng,
                }
                for st in route.stops
            ],
            "total_distance_miles": round(route.total_distance_miles, 2),
            "total_duration_minutes": round(route.total_duration_minutes, 1),
        }
    }
```

Add to the `TOOLS` list (after `find_yard_sales` entry):

```python
ToolDef(
    name="plan_route",
    description=(
        "Plan an ordered driving route through selected yard sales. "
        "Returns stops in visit order with ETAs and in-window flags. "
        "Requires start_location {lat, lng} and 1-10 sale_ids."
    ),
    input_schema=ToolInputSchema(
        type="object",
        properties={
            "sale_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Yard sale IDs to include, 1-10.",
            },
            "start_location": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lng": {"type": "number"},
                },
                "required": ["lat", "lng"],
                "description": "Starting coordinates for the route.",
            },
        },
        required=["sale_ids", "start_location"],
    ),
    handler=plan_route_handler,
),
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/plugins/yardsailing/ -v`
Expected: new tests PASS, existing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/tools.py backend/tests/plugins/yardsailing/test_plan_route_tool.py
git commit -m "feat(yardsailing): plan_route LLM tool with sale_ids input"
```

---

### Task 4: Add `POST /api/plugins/yardsailing/plan_route` HTTP endpoint

**Files:**
- Modify: `backend/app/plugins/yardsailing/routes.py`
- Modify: `backend/tests/plugins/yardsailing/test_routes.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/plugins/yardsailing/test_routes.py`:

```python
@pytest.mark.asyncio
async def test_plan_route_endpoint_returns_ordered_stops(
    client, auth_headers, seed_two_sales
):
    sale_ids = seed_two_sales
    resp = await client.post(
        "/api/plugins/yardsailing/plan_route",
        json={
            "sale_ids": sale_ids,
            "start_location": {"lat": 0.0, "lng": 0.0},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "route" in body
    assert len(body["route"]["stops"]) == 2


@pytest.mark.asyncio
async def test_plan_route_endpoint_rejects_over_cap(client, auth_headers):
    resp = await client.post(
        "/api/plugins/yardsailing/plan_route",
        json={
            "sale_ids": list(range(1, 12)),
            "start_location": {"lat": 0.0, "lng": 0.0},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
```

If `seed_two_sales` fixture does not exist yet, add it to `backend/tests/plugins/yardsailing/conftest.py`:

```python
@pytest.fixture
async def seed_two_sales(db_session, user_fixture):
    from app.plugins.yardsailing.services import CreateSaleInput, create_sale, list_recent_sales
    await create_sale(db_session, user_fixture, CreateSaleInput(
        title="One", address="100 Main St", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
    ))
    await create_sale(db_session, user_fixture, CreateSaleInput(
        title="Two", address="200 Main St", description=None,
        start_date="2026-04-14", end_date=None,
        start_time="08:00", end_time="12:00",
    ))
    all_sales = await list_recent_sales(db_session, limit=10)
    return [s.id for s in all_sales]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/plugins/yardsailing/test_routes.py::test_plan_route_endpoint_returns_ordered_stops -v`
Expected: FAIL with 404 or similar.

- [ ] **Step 3: Add the endpoint**

Edit `backend/app/plugins/yardsailing/routes.py`. Add near existing routes:

```python
from pydantic import BaseModel

from .routing import MAX_STOPS
from .tools import plan_route_handler


class StartLocation(BaseModel):
    lat: float
    lng: float


class PlanRouteRequest(BaseModel):
    sale_ids: list[int]
    start_location: StartLocation


@router.post("/plan_route")
async def plan_route_endpoint(
    body: PlanRouteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(body.sale_ids) > MAX_STOPS:
        raise HTTPException(status_code=400, detail=f"max {MAX_STOPS} stops")
    if not body.sale_ids:
        raise HTTPException(status_code=400, detail="sale_ids required")
    result = await plan_route_handler(
        {
            "sale_ids": body.sale_ids,
            "start_location": body.start_location.model_dump(),
        },
        user=user,
        db=db,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
```

(If `User`, `get_current_user`, `get_db`, `AsyncSession`, `HTTPException` aren't already imported at top of the file, add them — follow the pattern of the existing `POST /sales` route.)

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/plugins/yardsailing/test_routes.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plugins/yardsailing/routes.py backend/tests/plugins/yardsailing/test_routes.py backend/tests/plugins/yardsailing/conftest.py
git commit -m "feat(yardsailing): POST /plan_route HTTP endpoint"
```

---

## Stage 3: Mobile integration

### Task 5: API client for `plan_route`

**Files:**
- Modify: `mobile/src/api/` (add a new `yardsailing.ts` or extend existing)

- [ ] **Step 1: Check where current yardsailing calls live**

Run: `grep -rn "plugins/yardsailing" mobile/src/api/ | head`

If an existing file like `mobile/src/api/yardsailing.ts` exists, add to it. Otherwise create it.

- [ ] **Step 2: Add typed client function**

In `mobile/src/api/yardsailing.ts`:

```typescript
import { apiClient } from "./client"; // adjust to actual axios instance path

export interface RouteStop {
  sale_id: number;
  eta_minutes: number;
  in_window: boolean;
  title: string;
  address: string;
  lat: number;
  lng: number;
}

export interface Route {
  stops: RouteStop[];
  total_distance_miles: number;
  total_duration_minutes: number;
}

export interface PlanRouteResponse {
  route: Route;
}

export async function planRoute(
  saleIds: number[],
  start: { lat: number; lng: number },
): Promise<PlanRouteResponse> {
  const { data } = await apiClient.post<PlanRouteResponse>(
    "/api/plugins/yardsailing/plan_route",
    { sale_ids: saleIds, start_location: start },
  );
  return data;
}
```

Verify that the axios instance import path matches the project convention (check another API file in `mobile/src/api/` first).

- [ ] **Step 3: Commit**

```bash
git add mobile/src/api/yardsailing.ts
git commit -m "feat(mobile): planRoute API client"
```

---

### Task 6: `RouteCard` component

**Files:**
- Create: `mobile/src/chat/RouteCard.tsx`

- [ ] **Step 1: Create the component**

Create `mobile/src/chat/RouteCard.tsx`:

```tsx
import React from "react";
import { Linking, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { Route, RouteStop } from "../api/yardsailing";

interface Props {
  route: Route;
}

export function RouteCard({ route }: Props) {
  const openInMaps = () => {
    if (route.stops.length === 0) return;
    const url =
      Platform.OS === "ios"
        ? buildAppleMapsUrl(route.stops)
        : buildGoogleMapsUrl(route.stops);
    Linking.openURL(url);
  };

  return (
    <View style={styles.wrapper}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          Route · {route.stops.length} stops
        </Text>
        <Text style={styles.headerMeta}>
          {route.total_distance_miles.toFixed(1)} mi · {Math.round(route.total_duration_minutes)} min
        </Text>
      </View>
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {route.stops.map((stop, idx) => (
          <View key={stop.sale_id} style={styles.stop}>
            <View style={styles.stopNum}>
              <Text style={styles.stopNumText}>{idx + 1}</Text>
            </View>
            <View style={styles.stopBody}>
              <Text style={styles.stopTitle} numberOfLines={1}>{stop.title}</Text>
              <Text style={styles.stopAddr} numberOfLines={1}>{stop.address}</Text>
              <View style={styles.stopMetaRow}>
                <Text style={styles.stopEta}>ETA {Math.round(stop.eta_minutes)} min</Text>
                <View
                  style={[
                    styles.badge,
                    stop.in_window ? styles.badgeOk : styles.badgeLate,
                  ]}
                >
                  <Text
                    style={[
                      styles.badgeText,
                      stop.in_window ? styles.badgeOkText : styles.badgeLateText,
                    ]}
                  >
                    {stop.in_window ? "in window" : "late"}
                  </Text>
                </View>
              </View>
            </View>
          </View>
        ))}
      </ScrollView>
      <Pressable style={styles.button} onPress={openInMaps}>
        <Text style={styles.buttonText}>Open in Maps</Text>
      </Pressable>
    </View>
  );
}

function buildAppleMapsUrl(stops: RouteStop[]): string {
  const params = stops.map((s) => `daddr=${s.lat},${s.lng}`).join("&");
  return `http://maps.apple.com/?${params}`;
}

function buildGoogleMapsUrl(stops: RouteStop[]): string {
  const destination = stops[stops.length - 1];
  const waypoints = stops
    .slice(0, -1)
    .map((s) => `${s.lat},${s.lng}`)
    .join("|");
  const base = "https://www.google.com/maps/dir/?api=1";
  const dest = `&destination=${destination.lat},${destination.lng}`;
  const wp = waypoints ? `&waypoints=${encodeURIComponent(waypoints)}` : "";
  return `${base}${dest}${wp}`;
}

const styles = StyleSheet.create({
  wrapper: {
    marginHorizontal: 12,
    marginVertical: 6,
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    overflow: "hidden",
  },
  header: {
    padding: 12,
    backgroundColor: "#f8fafc",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  headerTitle: { fontSize: 15, fontWeight: "700", color: "#0f172a" },
  headerMeta: { fontSize: 12, color: "#64748b", marginTop: 2 },
  list: { maxHeight: 320 },
  listContent: { padding: 8 },
  stop: { flexDirection: "row", padding: 8 },
  stopNum: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: "#2563eb",
    alignItems: "center", justifyContent: "center",
    marginRight: 10, marginTop: 2,
  },
  stopNumText: { color: "#fff", fontWeight: "700", fontSize: 13 },
  stopBody: { flex: 1 },
  stopTitle: { fontSize: 14, fontWeight: "700", color: "#0f172a" },
  stopAddr: { fontSize: 12, color: "#475569", marginTop: 1 },
  stopMetaRow: { flexDirection: "row", alignItems: "center", marginTop: 4 },
  stopEta: { fontSize: 12, color: "#334155", marginRight: 8 },
  badge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  badgeOk: { backgroundColor: "#dcfce7" },
  badgeLate: { backgroundColor: "#fef3c7" },
  badgeText: { fontSize: 11, fontWeight: "600" },
  badgeOkText: { color: "#166534" },
  badgeLateText: { color: "#92400e" },
  button: {
    backgroundColor: "#2563eb",
    padding: 12,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
```

- [ ] **Step 2: Commit**

```bash
git add mobile/src/chat/RouteCard.tsx
git commit -m "feat(mobile): RouteCard component with Open in Maps handoff"
```

---

### Task 7: Multi-select mode and PlanRouteButton in `DataCard`

**Files:**
- Modify: `mobile/src/chat/DataCard.tsx`

- [ ] **Step 1: Add multi-select state and row tick UI**

Edit `mobile/src/chat/DataCard.tsx`. Add imports at top:

```tsx
import { planRoute } from "../api/yardsailing";
import { RouteCard } from "./RouteCard";
import type { Route as PlannedRoute } from "../api/yardsailing";
```

Inside the component, when `displayHint === "map"`, replace the current block with a stateful version:

```tsx
if (displayHint === "map" && data && typeof data === "object" && "sales" in data) {
  const sales = ((data as { sales: SaleWithDistance[] }).sales ?? []);
  const [selectMode, setSelectMode] = React.useState(false);
  const [ticked, setTicked] = React.useState<Set<number>>(new Set());
  const [route, setRoute] = React.useState<PlannedRoute | null>(null);
  const [planning, setPlanning] = React.useState(false);
  const [planError, setPlanError] = React.useState<string | null>(null);

  const MAX_STOPS = 10;

  if (sales.length === 0) {
    return (
      <View style={styles.header}>
        <Text style={styles.headerText}>No yard sales found nearby.</Text>
      </View>
    );
  }

  if (route) {
    return <RouteCard route={route} />;
  }

  const toggle = (id: number) => {
    setTicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else {
        if (next.size >= MAX_STOPS) return prev;  // cap
        next.add(id);
      }
      return next;
    });
  };

  const plan = async () => {
    setPlanning(true);
    setPlanError(null);
    try {
      // TODO: replace with actual device location — see Task 8
      const start = await getCurrentStartLocation();
      const ids = Array.from(ticked);
      const resp = await planRoute(ids, start);
      setRoute(resp.route);
    } catch (e) {
      setPlanError("Could not plan route.");
    } finally {
      setPlanning(false);
    }
  };

  return (
    <View style={styles.wrapper}>
      <View style={styles.topRow}>
        <Text style={styles.headerText}>
          {sales.length} yard sale{sales.length === 1 ? "" : "s"}
          {selectMode ? ` · ${ticked.size} selected` : ""}
        </Text>
        <Pressable
          onPress={() => {
            setSelectMode(!selectMode);
            setTicked(new Set());
          }}
        >
          <Text style={styles.selectToggle}>
            {selectMode ? "Done" : "Select"}
          </Text>
        </Pressable>
      </View>
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {sales.map((sale) => {
          const checked = ticked.has(sale.id);
          return (
            <Pressable
              key={sale.id}
              style={[styles.card, checked && styles.cardChecked]}
              onPress={() => (selectMode ? toggle(sale.id) : setSelected(sale))}
            >
              {selectMode ? (
                <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
                  {checked ? <Text style={styles.checkMark}>✓</Text> : null}
                </View>
              ) : null}
              <View style={{ flex: 1 }}>
                <View style={styles.cardRow}>
                  <Text style={styles.title} numberOfLines={1}>{sale.title}</Text>
                  {sale.distance_miles != null ? (
                    <Text style={styles.distance}>{sale.distance_miles.toFixed(1)} mi</Text>
                  ) : null}
                </View>
                <Text style={styles.address} numberOfLines={1}>{sale.address}</Text>
                {(sale.start_date || sale.start_time) ? (
                  <Text style={styles.meta} numberOfLines={1}>
                    {sale.start_date ?? ""}
                    {sale.start_time ? ` · ${sale.start_time}` : ""}
                    {sale.end_time ? `–${sale.end_time}` : ""}
                  </Text>
                ) : null}
                {sale.tags && sale.tags.length > 0 ? (
                  <View style={styles.tagRow}>
                    {sale.tags.slice(0, 4).map((t) => (
                      <View key={t} style={styles.tagChip}>
                        <Text style={styles.tagText}>{t}</Text>
                      </View>
                    ))}
                  </View>
                ) : null}
                {!selectMode ? <Text style={styles.chev}>›</Text> : null}
              </View>
            </Pressable>
          );
        })}
      </ScrollView>
      {selectMode && ticked.size >= 2 ? (
        <Pressable
          style={styles.planButton}
          onPress={plan}
          disabled={planning}
        >
          <Text style={styles.planButtonText}>
            {planning ? "Planning…" : `Plan Route (${ticked.size})`}
          </Text>
        </Pressable>
      ) : null}
      {planError ? <Text style={styles.planError}>{planError}</Text> : null}
      <SaleDetailsModal sale={selected} onClose={() => setSelected(null)} />
    </View>
  );
}
```

Add to the `StyleSheet.create({ ... })` block:

```ts
topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 4, marginBottom: 8 },
selectToggle: { fontSize: 13, color: "#2563eb", fontWeight: "600" },
cardChecked: { backgroundColor: "#eff6ff", borderColor: "#93c5fd" },
checkbox: {
  width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: "#cbd5e1",
  marginRight: 10, alignItems: "center", justifyContent: "center",
},
checkboxChecked: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
checkMark: { color: "#fff", fontSize: 13, fontWeight: "700" },
planButton: { backgroundColor: "#2563eb", padding: 12, borderRadius: 10, alignItems: "center", marginTop: 8 },
planButtonText: { color: "#fff", fontWeight: "700", fontSize: 14 },
planError: { color: "#b91c1c", textAlign: "center", marginTop: 6, fontSize: 12 },
```

Change `card` to be a row layout (so the checkbox sits beside content):

```ts
card: {
  backgroundColor: "#fff",
  borderRadius: 10,
  borderWidth: 1,
  borderColor: "#e2e8f0",
  padding: 12,
  marginBottom: 8,
  position: "relative",
  flexDirection: "row",
  alignItems: "flex-start",
},
```

(Remove the `position: "absolute"` behavior of `.chev` if it conflicts with row layout — set `chev` to `marginLeft: 8, alignSelf: "center"`.)

Add a `getCurrentStartLocation` helper (inline in this file is fine, or extract):

```tsx
async function getCurrentStartLocation(): Promise<{ lat: number; lng: number }> {
  // Placeholder — actual expo-location integration in Task 8.
  return { lat: 0, lng: 0 };
}
```

- [ ] **Step 2: Hand-test on simulator**

Run the app, trigger a `find_yard_sales` query in chat, tap "Select", tick 2 sales, tap "Plan Route". Verify the RouteCard renders (with a placeholder start, stops will be poorly ordered but the flow works).

- [ ] **Step 3: Commit**

```bash
git add mobile/src/chat/DataCard.tsx
git commit -m "feat(mobile): multi-select + Plan Route in sale list"
```

---

### Task 8: Wire real device location into start point

**Files:**
- Modify: `mobile/src/chat/DataCard.tsx`

- [ ] **Step 1: Check if `expo-location` is already installed**

Run: `grep -n "expo-location" mobile/package.json`

If missing, install:

```bash
cd mobile && npx expo install expo-location
```

- [ ] **Step 2: Replace the placeholder**

Edit `mobile/src/chat/DataCard.tsx`. Replace `getCurrentStartLocation`:

```tsx
import * as Location from "expo-location";

async function getCurrentStartLocation(): Promise<{ lat: number; lng: number }> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  if (status !== "granted") {
    throw new Error("Location permission denied");
  }
  const pos = await Location.getCurrentPositionAsync({});
  return { lat: pos.coords.latitude, lng: pos.coords.longitude };
}
```

- [ ] **Step 3: Hand-test**

On device/simulator with location enabled: tick sales, plan route, verify the stop order matches expectation based on your actual location.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/chat/DataCard.tsx mobile/package.json mobile/package-lock.json
git commit -m "feat(mobile): use device GPS as route start location"
```

---

## Stage 4: Chat-side rendering for LLM-returned routes

### Task 9: `DataCard` handles `displayHint="route"`

**Files:**
- Modify: `mobile/src/chat/DataCard.tsx`
- Modify: `backend/app/plugins/yardsailing/tools.py` (emit displayHint)

- [ ] **Step 1: Backend — annotate plan_route result with displayHint**

Check how `find_yard_sales` currently gets `displayHint="map"`. If it's added by the chat service based on tool name, extend that mapping. If it comes from the tool result itself, edit `plan_route_handler` in `tools.py` to include it.

Run: `grep -rn "display_hint\|displayHint" backend/app/ | head`

Based on what you find, add `"display_hint": "route"` to the plan_route handler response (alongside `"route": {...}`).

- [ ] **Step 2: Mobile — add render branch**

Edit `mobile/src/chat/DataCard.tsx`. Above the existing `"map"` branch, add:

```tsx
if (displayHint === "route" && data && typeof data === "object" && "route" in data) {
  const route = (data as { route: PlannedRoute }).route;
  return <RouteCard route={route} />;
}
```

- [ ] **Step 3: Hand-test via chat**

In chat, something like: "plan a route for sale IDs 1, 2, 3 starting at 40.7, -74.0". Verify LLM calls `plan_route` and a `RouteCard` renders in the chat stream.

- [ ] **Step 4: Commit**

```bash
git add backend/app/plugins/yardsailing/tools.py mobile/src/chat/DataCard.tsx
git commit -m "feat(yardsailing): chat renders plan_route results as RouteCard"
```

---

### Task 10: Final QA pass and full test run

- [ ] **Step 1: Run backend test suite**

Run: `cd backend && pytest -v`
Expected: all tests PASS, no new warnings.

- [ ] **Step 2: Manual mobile QA checklist**

- Tick 2 sales, tap Plan Route, verify ordered card.
- Tick 10 sales, verify 11th tap is blocked.
- Mix in-window and out-of-window sales (set one with `end_time` in the past); verify amber "late" badge.
- iOS: tap Open in Maps, verify Apple Maps opens with multi-stop.
- Android: tap Open in Maps, verify Google Maps browser/app opens with waypoints.
- Chat path: "plan a route through these 3 sales (ids: X, Y, Z) from my location", verify LLM calls tool and card renders.

- [ ] **Step 3: Commit any fixes as separate commits as you find them**

---

## Out of scope (do not add)

- Saved/named routes or any persistence.
- Live re-routing.
- Traffic-aware ETAs.
- Strict-mode window filtering (only soft).
- Multi-day routes.
