from dataclasses import dataclass
from datetime import date, datetime

import pytest

from app.plugins.custody.schedules import ExpectedPickup, expected_pickups


@dataclass
class FakeSchedule:
    id: str
    start_date: str
    interval_weeks: int
    weekdays: str
    pickup_time: str
    dropoff_time: str


@dataclass
class FakeException:
    date: str
    kind: str  # skip | override
    override_pickup_at: datetime | None = None
    override_dropoff_at: datetime | None = None


def _s(**kw) -> FakeSchedule:
    base = dict(
        id="sch1", start_date="2026-01-02",  # a Friday
        interval_weeks=1, weekdays="4",       # Fridays
        pickup_time="17:00", dropoff_time="19:00",
    )
    base.update(kw)
    return FakeSchedule(**base)


def test_weekly_single_day_generates_fridays():
    sched = _s()
    got = expected_pickups(sched, [], date(2026, 1, 1), date(2026, 1, 31))
    assert [p.expected_date for p in got] == [
        date(2026, 1, 2), date(2026, 1, 9), date(2026, 1, 16),
        date(2026, 1, 23), date(2026, 1, 30),
    ]


def test_eow_skips_off_weeks():
    sched = _s(interval_weeks=2)
    got = expected_pickups(sched, [], date(2026, 1, 1), date(2026, 1, 31))
    assert [p.expected_date for p in got] == [
        date(2026, 1, 2), date(2026, 1, 16), date(2026, 1, 30),
    ]


def test_multiple_weekdays():
    sched = _s(weekdays="4,5,6")  # Fri, Sat, Sun
    got = expected_pickups(sched, [], date(2026, 1, 2), date(2026, 1, 4))
    assert [p.expected_date for p in got] == [
        date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4),
    ]


def test_skip_exception_removes_occurrence():
    sched = _s()
    skips = [FakeException(date="2026-01-09", kind="skip")]
    got = expected_pickups(sched, skips, date(2026, 1, 1), date(2026, 1, 20))
    assert [p.expected_date for p in got] == [date(2026, 1, 2), date(2026, 1, 16)]


def test_override_exception_replaces_times():
    sched = _s()
    over_pickup = datetime(2026, 1, 9, 15, 30)
    over_drop = datetime(2026, 1, 9, 18, 0)
    overrides = [FakeException(
        date="2026-01-09", kind="override",
        override_pickup_at=over_pickup, override_dropoff_at=over_drop,
    )]
    got = expected_pickups(sched, overrides, date(2026, 1, 9), date(2026, 1, 9))
    assert len(got) == 1
    p = got[0]
    assert p.expected_pickup_at == over_pickup
    assert p.expected_dropoff_at == over_drop


def test_pickup_time_applied_to_date():
    sched = _s(pickup_time="08:30", dropoff_time="10:15")
    got = expected_pickups(sched, [], date(2026, 1, 2), date(2026, 1, 2))
    assert got[0].expected_pickup_at == datetime(2026, 1, 2, 8, 30)
    assert got[0].expected_dropoff_at == datetime(2026, 1, 2, 10, 15)


def test_returns_expected_pickup_dataclass_with_schedule_id():
    sched = _s(id="abc")
    got = expected_pickups(sched, [], date(2026, 1, 2), date(2026, 1, 2))
    assert isinstance(got[0], ExpectedPickup)
    assert got[0].schedule_id == "abc"


def test_empty_when_range_before_start_date():
    sched = _s(start_date="2026-06-01")
    got = expected_pickups(sched, [], date(2026, 1, 1), date(2026, 1, 31))
    assert got == []
