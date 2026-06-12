"""Volatility compression: Bollinger/Keltner squeeze + realized volatility."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .atr import atr


def realized_vol(df: pd.DataFrame, window: int = 20, periods_per_year: int = 252) -> float | None:
    if len(df) < window + 1:
        return None
    rets = np.log(df["close"] / df["close"].shift(1)).dropna().iloc[-window:]
    if len(rets) < 2:
        return None
    return float(rets.std() * np.sqrt(periods_per_year))


def bollinger(df: pd.DataFrame, period: int = 20, mult: float = 2.0):
    ma = df["close"].rolling(period).mean()
    sd = df["close"].rolling(period).std()
    return ma - mult * sd, ma, ma + mult * sd


def keltner(df: pd.DataFrame, period: int = 20, mult: float = 1.5):
    ma = df["close"].ewm(span=period, adjust=False).mean()
    a = atr(df, period)
    return ma - mult * a, ma, ma + mult * a


def squeeze_on(df: pd.DataFrame, period: int = 20) -> bool | None:
    """TTM-style squeeze: Bollinger Bands inside Keltner Channels (compression)."""
    if len(df) < period + 1:
        return None
    bb_lo, _, bb_hi = bollinger(df, period)
    kc_lo, _, kc_hi = keltner(df, period)
    if np.isnan(bb_lo.iloc[-1]) or np.isnan(kc_lo.iloc[-1]):
        return None
    return bool(bb_lo.iloc[-1] > kc_lo.iloc[-1] and bb_hi.iloc[-1] < kc_hi.iloc[-1])


def bandwidth(df: pd.DataFrame, period: int = 20) -> float | None:
    if len(df) < period + 1:
        return None
    bb_lo, ma, bb_hi = bollinger(df, period)
    if np.isnan(ma.iloc[-1]) or ma.iloc[-1] == 0:
        return None
    return float((bb_hi.iloc[-1] - bb_lo.iloc[-1]) / ma.iloc[-1])
