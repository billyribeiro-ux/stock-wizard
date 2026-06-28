"""Market regime classification — trend vs range.

Uses the Kaufman Efficiency Ratio (ER): net directional displacement over a window divided
by the total path length. ER → 1 means a clean directional move (trending); ER → 0 means
the path wandered without getting anywhere (choppy / range-bound). This is timeframe-robust
and computed point-in-time (each bar's label uses only prior closes), so it is safe to use
for no-lookahead backtest segmentation.
"""

from __future__ import annotations

import pandas as pd

TREND = "trend"
RANGE = "range"


def efficiency_ratio(closes: pd.Series, window: int = 20) -> pd.Series:
    """Kaufman Efficiency Ratio per bar (NaN until ``window`` bars are available)."""
    change = closes.diff(window).abs()
    volatility = closes.diff().abs().rolling(window).sum()
    return change / volatility.replace(0, pd.NA)


def regime_labels(closes: pd.Series, window: int = 20, trend_er: float = 0.30) -> list[str]:
    """Per-bar ``trend``/``range`` labels. Bars before the window is filled default to RANGE
    (no established trend yet)."""
    er = efficiency_ratio(closes, window)
    return [TREND if (v is not None and v == v and v >= trend_er) else RANGE for v in er]


def classify_regime(closes: pd.Series, window: int = 20, trend_er: float = 0.30) -> str:
    """Regime label for the most recent bar."""
    labels = regime_labels(closes, window, trend_er)
    return labels[-1] if labels else RANGE
