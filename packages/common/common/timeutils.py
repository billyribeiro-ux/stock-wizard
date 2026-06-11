"""Timezone / market-session helpers. Store UTC, reason about sessions in exchange tz."""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_exchange(dt: datetime, tz: ZoneInfo = NY) -> datetime:
    return to_utc(dt).astimezone(tz)


def is_regular_hours(dt: datetime, tz: ZoneInfo = NY) -> bool:
    """True if dt falls within US equity regular trading hours (weekday 9:30–16:00)."""
    local = to_exchange(dt, tz)
    if local.weekday() >= 5:
        return False
    return RTH_OPEN <= local.time() < RTH_CLOSE


def minutes_to_close(dt: datetime, tz: ZoneInfo = NY) -> float:
    """Minutes remaining until the regular-session close (0DTE timing). 0 outside RTH."""
    local = to_exchange(dt, tz)
    close = local.replace(hour=16, minute=0, second=0, microsecond=0)
    delta = (close - local).total_seconds() / 60.0
    return max(0.0, delta)


def year_fraction_to_close(dt: datetime, tz: ZoneInfo = NY) -> float:
    """Time-to-expiry (in years) until today's close — for 0DTE greeks. Floored small."""
    mins = minutes_to_close(dt, tz)
    # minutes in a 252-trading-day * 6.5h year ≈ 98280; floor avoids T->0 blowups.
    return max(mins / (252 * 6.5 * 60), 1e-6)
