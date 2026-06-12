"""Key reference levels: prior-session high/low/close, opening range, gaps, round numbers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def _et_date(df: pd.DataFrame):
    idx = df.index
    return idx.tz_convert("America/New_York").date if idx.tz is not None else idx.date


@dataclass(frozen=True)
class SessionLevels:
    prev_high: float | None
    prev_low: float | None
    prev_close: float | None
    today_open: float | None
    opening_range_high: float | None
    opening_range_low: float | None
    gap_pct: float | None


def session_levels(df: pd.DataFrame, opening_minutes: int = 30) -> SessionLevels | None:
    if df.empty:
        return None
    days = pd.Index(_et_date(df), name="d")
    unique_days = list(dict.fromkeys(days))
    if not unique_days:
        return None
    today = unique_days[-1]
    today_mask = days == today
    today_df = df[today_mask]

    prev_high = prev_low = prev_close = None
    if len(unique_days) >= 2:
        prev = unique_days[-2]
        prev_df = df[days == prev]
        if not prev_df.empty:
            prev_high = float(prev_df["high"].max())
            prev_low = float(prev_df["low"].min())
            prev_close = float(prev_df["close"].iloc[-1])

    today_open = float(today_df["open"].iloc[0]) if not today_df.empty else None

    # Opening range = first N minutes of today's session (intraday only).
    or_high = or_low = None
    if not today_df.empty and today_df.index.tz is not None:
        start = today_df.index[0]
        window = today_df[today_df.index <= start + pd.Timedelta(minutes=opening_minutes)]
        if not window.empty:
            or_high = float(window["high"].max())
            or_low = float(window["low"].min())

    gap_pct = None
    if today_open is not None and prev_close:
        gap_pct = (today_open - prev_close) / prev_close

    return SessionLevels(prev_high, prev_low, prev_close, today_open, or_high, or_low, gap_pct)


def nearest_round_number(price: float, step: float | None = None) -> float:
    """Nearest psychologically-significant round level."""
    if step is None:
        # scale step to price magnitude
        if price >= 1000:
            step = 50.0
        elif price >= 100:
            step = 5.0
        elif price >= 10:
            step = 1.0
        else:
            step = 0.5
    return round(price / step) * step
