"""VWAP and Anchored VWAP — institutional average-price reference levels."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import typical_price


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Cumulative VWAP reset each calendar day (exchange-local index assumed tz-aware)."""
    tp = typical_price(df)
    pv = tp * df["volume"]
    day = df.index.tz_convert("America/New_York").date if df.index.tz is not None else df.index.date
    grouper = pd.Index(day, name="day")
    cum_pv = pv.groupby(grouper).cumsum()
    cum_vol = df["volume"].groupby(grouper).cumsum().replace(0, np.nan)
    return cum_pv / cum_vol


def anchored_vwap(df: pd.DataFrame, anchor_idx: int) -> pd.Series:
    """VWAP anchored from `anchor_idx` (e.g. a swing high/low or event bar) forward."""
    sub = df.iloc[anchor_idx:]
    tp = typical_price(sub)
    pv = (tp * sub["volume"]).cumsum()
    vol = sub["volume"].cumsum().replace(0, np.nan)
    return pv / vol


def vwap_distance_atr(df: pd.DataFrame, atr_value: float | None) -> float | None:
    """Distance of last close from session VWAP, in ATR units (signed)."""
    if atr_value is None or atr_value <= 0 or df.empty:
        return None
    vw = session_vwap(df)
    last_vwap = vw.iloc[-1]
    if np.isnan(last_vwap):
        return None
    return float((df["close"].iloc[-1] - last_vwap) / atr_value)
