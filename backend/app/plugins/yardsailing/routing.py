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
