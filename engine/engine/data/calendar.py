"""Exchange calendar helpers (thin wrapper over pandas-market-calendars)."""

from __future__ import annotations

from datetime import date

import pandas_market_calendars as mcal

_NYSE = mcal.get_calendar("NYSE")


def is_trading_day(d: date) -> bool:
    sched = _NYSE.schedule(start_date=d.isoformat(), end_date=d.isoformat())
    return not sched.empty


def last_trading_day(d: date) -> date:
    sched = _NYSE.schedule(start_date=(d.replace(day=1)).isoformat(), end_date=d.isoformat())
    if sched.empty:
        return d
    return sched.index[-1].date()
