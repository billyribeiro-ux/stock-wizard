"""Timezone / session helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from common.timeutils import (
    is_regular_hours,
    minutes_to_close,
    to_exchange,
    year_fraction_to_close,
)


def test_regular_hours_weekday_midday():
    # 2026-06-11 is a Thursday; 14:30 UTC = 10:30 ET (RTH).
    dt = datetime(2026, 6, 11, 14, 30, tzinfo=UTC)
    assert is_regular_hours(dt)


def test_not_regular_hours_overnight():
    dt = datetime(2026, 6, 11, 3, 0, tzinfo=UTC)  # 23:00 ET prev day
    assert not is_regular_hours(dt)


def test_not_regular_hours_weekend():
    dt = datetime(2026, 6, 13, 15, 0, tzinfo=UTC)  # Saturday
    assert not is_regular_hours(dt)


def test_minutes_to_close_decreases():
    early = datetime(2026, 6, 11, 14, 0, tzinfo=UTC)  # 10:00 ET
    late = datetime(2026, 6, 11, 19, 0, tzinfo=UTC)  # 15:00 ET
    assert minutes_to_close(early) > minutes_to_close(late) > 0


def test_year_fraction_floored_positive():
    after_close = datetime(2026, 6, 11, 21, 0, tzinfo=UTC)  # 17:00 ET
    assert year_fraction_to_close(after_close) >= 1e-6


def test_to_exchange_converts():
    dt = datetime(2026, 6, 11, 14, 30, tzinfo=UTC)
    local = to_exchange(dt)
    assert local.hour == 10 and local.minute == 30
