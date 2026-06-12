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


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume — cumulative signed volume by close direction."""
    direction = np.sign(df["close"].diff().fillna(0.0))
    return (direction * df["volume"]).cumsum()


def obv_slope(df: pd.DataFrame, window: int = 20) -> float | None:
    """Normalized slope of OBV over `window` bars (accumulation/distribution gauge)."""
    if len(df) < window:
        return None
    series = obv(df).iloc[-window:].to_numpy(dtype=float)
    scale = np.abs(series).mean()
    if scale <= 0:
        return None
    x = np.arange(window, dtype=float)
    return float(np.polyfit(x, series, 1)[0] / scale)


def effort_vs_result(df: pd.DataFrame) -> float | None:
    """Volume (effort) vs price progress (result) on the last bar.

    High ratio = lots of volume, little movement = absorption.
    """
    if len(df) < 2:
        return None
    rng = float(df["high"].iloc[-1] - df["low"].iloc[-1])
    vol = float(df["volume"].iloc[-1])
    if rng <= 0:
        return None
    avg_vol = float(df["volume"].iloc[-20:].mean()) if len(df) >= 20 else vol
    if avg_vol <= 0:
        return None
    return (vol / avg_vol) / (rng / df["close"].iloc[-1] / 0.01 + 1e-9)


def volume_dry_up(df: pd.DataFrame, lookback: int = 20) -> bool | None:
    """True when the latest bar's volume is in the bottom quartile of the lookback."""
    if len(df) < lookback + 1:
        return None
    recent = df["volume"].iloc[-(lookback + 1) : -1]
    q25 = np.percentile(recent.to_numpy(dtype=float), 25)
    return bool(df["volume"].iloc[-1] <= q25)
