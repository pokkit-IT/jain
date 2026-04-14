import pytest
from datetime import datetime

from app.plugins.yardsailing.routing import (
    MAX_STOPS,
    LatLng,
    RouteStop,
    Route,
    SaleInput,
    haversine_miles,
    plan_route,
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


def _sale(sid, lat, lng, end=None):
    return SaleInput(id=sid, lat=lat, lng=lng, end_datetime=end)


def test_plan_route_orders_by_nearest_neighbor_when_clear():
    # Start at origin. Three sales on a line: (0,0.01) (0,0.02) (0,0.05).
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
        lng=50.0 / 69.0,  # ~50 miles east at the equator
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
    assert route.total_distance_miles >= 0.1
