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
