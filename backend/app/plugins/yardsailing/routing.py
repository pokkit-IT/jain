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
