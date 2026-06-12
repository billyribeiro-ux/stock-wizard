"""Build a supervised dataset from OHLCV history.

Produces an as-of-safe feature matrix (every feature uses only past data) and a
forward-return label, vectorized with pandas for speed (much faster than running the
full FeatureFactory per bar). Used to train setup-success models and to detect
anomalies / regimes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..features.atr import atr
from ..features.base import ohlcv_to_frame
from ..schemas import OHLCV

FEATURE_NAMES = [
    "ret_1",
    "ret_5",
    "ret_10",
    "atr_norm",
    "range_atr",
    "rvol",
    "vol_slope",
    "dist_sma20_atr",
    "rsi14",
    "bb_pctb",
    "obv_slope",
]


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def compute_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized as-of-safe features (one row per bar)."""
    out = pd.DataFrame(index=df.index)
    close = df["close"]
    a = atr(df, 14)
    out["ret_1"] = close.pct_change()
    out["ret_5"] = close.pct_change(5)
    out["ret_10"] = close.pct_change(10)
    out["atr_norm"] = a / close
    out["range_atr"] = (df["high"] - df["low"]) / a
    med_vol = df["volume"].rolling(20).median()
    out["rvol"] = df["volume"] / med_vol
    out["vol_slope"] = df["volume"].pct_change().rolling(5).mean()
    sma20 = close.rolling(20).mean()
    out["dist_sma20_atr"] = (close - sma20) / a
    out["rsi14"] = _rsi(close)
    bb_ma = close.rolling(20).mean()
    bb_sd = close.rolling(20).std()
    bb_lo, bb_hi = bb_ma - 2 * bb_sd, bb_ma + 2 * bb_sd
    out["bb_pctb"] = (close - bb_lo) / (bb_hi - bb_lo)
    direction = np.sign(close.diff().fillna(0.0))
    obv = (direction * df["volume"]).cumsum()
    out["obv_slope"] = obv.diff().rolling(20).mean() / df["volume"].rolling(20).mean()
    return out[FEATURE_NAMES]


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    feature_names: list[str]
    index: pd.DatetimeIndex
    forward_returns: np.ndarray


def build_dataset(ohlcv: OHLCV, horizon: int = 10, up_threshold: float = 0.0) -> Dataset | None:
    df = ohlcv_to_frame(ohlcv)
    if len(df) < 60 + horizon:
        return None
    feats = compute_feature_frame(df)
    fwd = df["close"].shift(-horizon) / df["close"] - 1.0
    label = (fwd > up_threshold).astype(int)

    mask = feats.notna().all(axis=1) & fwd.notna()
    feats, label, fwd = feats[mask], label[mask], fwd[mask]
    if len(feats) < 50:
        return None
    return Dataset(
        X=feats.to_numpy(dtype=float),
        y=label.to_numpy(dtype=int),
        feature_names=FEATURE_NAMES,
        index=feats.index,
        forward_returns=fwd.to_numpy(dtype=float),
    )
