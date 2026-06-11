"""Volume evidence: relative volume and the *subtle* multi-bar volume slope the
blueprint specifically calls out (slow accumulation a human would miss)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rvol(df: pd.DataFrame, lookback: int = 20) -> float | None:
    """Relative volume = current bar volume / median volume over prior `lookback` bars."""
    if len(df) < lookback + 1:
        return None
    baseline = df["volume"].iloc[-(lookback + 1) : -1].median()
    if baseline <= 0:
        return None
    return float(df["volume"].iloc[-1] / baseline)


def volume_slope(df: pd.DataFrame, window: int = 5) -> float | None:
    """Normalized slope of volume over the last `window` bars (OLS, scaled by mean).

    Positive => volume building (accumulation/effort rising); negative => drying up.
    """
    if len(df) < window:
        return None
    y = df["volume"].iloc[-window:].to_numpy(dtype=float)
    if y.mean() <= 0:
        return None
    x = np.arange(window, dtype=float)
    slope = np.polyfit(x, y, 1)[0]
    return float(slope / y.mean())


def up_down_volume_ratio(df: pd.DataFrame, lookback: int = 20) -> float | None:
    """Volume on up bars vs down bars over `lookback` — a crude accumulation gauge."""
    if len(df) < lookback:
        return None
    window = df.iloc[-lookback:]
    up = window.loc[window["close"] >= window["open"], "volume"].sum()
    down = window.loc[window["close"] < window["open"], "volume"].sum()
    if down <= 0:
        return float("inf") if up > 0 else None
    return float(up / down)


def volume_dry_up(df: pd.DataFrame, lookback: int = 20) -> bool | None:
    """True when the latest bar's volume is in the bottom quartile of the lookback."""
    if len(df) < lookback + 1:
        return None
    recent = df["volume"].iloc[-(lookback + 1) : -1]
    q25 = np.percentile(recent.to_numpy(dtype=float), 25)
    return bool(df["volume"].iloc[-1] <= q25)
