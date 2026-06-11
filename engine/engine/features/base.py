"""Feature factory primitives: a typed context and OHLCV<->DataFrame helpers.

Features are pure functions of an as-of-safe context. Everything here works on the
canonical ``OHLCV`` schema so features are unit-testable with synthetic data and never
touch the network or the database.
"""

from __future__ import annotations

import pandas as pd

from ..schemas import OHLCV


def ohlcv_to_frame(ohlcv: OHLCV) -> pd.DataFrame:
    """Convert an OHLCV series into a tz-aware, ts-indexed float DataFrame."""
    if not ohlcv.bars:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "vwap"]).rename_axis(
            "ts"
        )
    rows = [
        {
            "ts": b.ts,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": int(b.volume),
            "vwap": float(b.vwap) if b.vwap is not None else None,
        }
        for b in ohlcv.bars
    ]
    df = pd.DataFrame(rows).set_index("ts").sort_index()
    return df


def typical_price(df: pd.DataFrame) -> pd.Series:
    """(H + L + C) / 3 — the standard VWAP/profile price proxy."""
    return (df["high"] + df["low"] + df["close"]) / 3.0
