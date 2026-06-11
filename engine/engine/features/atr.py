"""Average True Range — the system's universal volatility yardstick.

Used everywhere to ATR-normalize distances so a "big move" means the same thing on
SPY and on a $5 stock.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ATR (RMA smoothing)."""
    tr = true_range(df)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def atr_last(df: pd.DataFrame, period: int = 14) -> float | None:
    if len(df) < period + 1:
        return None
    val = atr(df, period).iloc[-1]
    return float(val) if not np.isnan(val) else None
