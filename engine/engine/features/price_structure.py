"""Market structure: fractal swing points, HH/HL/LH/LL trend, BOS and CHoCH.

These power the Multi-Timeframe Market Structure scanner. A swing high at bar i is a
local maximum over a symmetric ``±k`` window; lows are symmetric. From the ordered
swing sequence we classify trend and detect Break of Structure (BOS) and Change of
Character (CHoCH).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class SwingType(str, Enum):
    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True)
class Swing:
    idx: int
    ts: pd.Timestamp
    price: float
    kind: SwingType


@dataclass(frozen=True)
class StructureState:
    trend: str  # "up" | "down" | "range"
    swings: list[Swing]
    last_bos: str | None  # "up" | "down" | None
    last_choch: str | None  # "up" | "down" | None
    last_swing_high: float | None
    last_swing_low: float | None


def find_swings(df: pd.DataFrame, k: int = 2) -> list[Swing]:
    """Fractal pivots: bar i is a swing high if its high is the max of [i-k, i+k]."""
    swings: list[Swing] = []
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    n = len(df)
    for i in range(k, n - k):
        window_hi = highs[i - k : i + k + 1]
        window_lo = lows[i - k : i + k + 1]
        if highs[i] == window_hi.max() and (window_hi.argmax() == k):
            swings.append(Swing(i, df.index[i], float(highs[i]), SwingType.HIGH))
        elif lows[i] == window_lo.min() and (window_lo.argmin() == k):
            swings.append(Swing(i, df.index[i], float(lows[i]), SwingType.LOW))
    return swings


def classify_structure(df: pd.DataFrame, k: int = 2) -> StructureState:
    """Derive trend + BOS/CHoCH from the swing sequence and the latest close."""
    swings = find_swings(df, k)
    highs = [s for s in swings if s.kind == SwingType.HIGH]
    lows = [s for s in swings if s.kind == SwingType.LOW]

    last_high = highs[-1].price if highs else None
    last_low = lows[-1].price if lows else None

    # Trend from the last two highs and last two lows.
    trend = "range"
    if len(highs) >= 2 and len(lows) >= 2:
        hh = highs[-1].price > highs[-2].price
        hl = lows[-1].price > lows[-2].price
        lh = highs[-1].price < highs[-2].price
        ll = lows[-1].price < lows[-2].price
        if hh and hl:
            trend = "up"
        elif lh and ll:
            trend = "down"

    # BOS: latest close breaks the most recent opposing swing in trend direction.
    close = float(df["close"].iloc[-1])
    last_bos: str | None = None
    if last_high is not None and close > last_high:
        last_bos = "up"
    elif last_low is not None and close < last_low:
        last_bos = "down"

    # CHoCH: a BOS against the prevailing trend (first sign of character change).
    last_choch: str | None = None
    if last_bos == "up" and trend == "down":
        last_choch = "up"
    elif last_bos == "down" and trend == "up":
        last_choch = "down"

    return StructureState(
        trend=trend,
        swings=swings,
        last_bos=last_bos,
        last_choch=last_choch,
        last_swing_high=last_high,
        last_swing_low=last_low,
    )
