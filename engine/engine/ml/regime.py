"""Unsupervised regime discovery via KMeans on feature vectors.

Clusters historical bars into regimes and characterizes each by its forward-return
bias, so the current bar's regime carries an empirical edge estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from ..features.base import ohlcv_to_frame
from ..schemas import OHLCV
from .dataset import compute_feature_frame


@dataclass
class RegimeResult:
    current_regime: int
    n_regimes: int
    regime_forward_bias: float  # mean forward return of the current regime's history
    regime_win_rate: float
    sample_size: int


def classify_regime(
    ohlcv: OHLCV, n_regimes: int = 4, horizon: int = 10, lookback: int = 500
) -> RegimeResult | None:
    df = ohlcv_to_frame(ohlcv)
    if len(df) < 80 + horizon:
        return None
    feats = compute_feature_frame(df)
    fwd = df["close"].shift(-horizon) / df["close"] - 1.0
    mask = feats.notna().all(axis=1)
    feats, fwd_aligned = feats[mask], fwd[mask]
    if len(feats) < 60:
        return None
    feats = feats.iloc[-lookback:]
    fwd_aligned = fwd_aligned.iloc[-lookback:]

    X = StandardScaler().fit_transform(feats.to_numpy(dtype=float))
    k = min(n_regimes, max(2, len(feats) // 25))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(X)
    current = int(labels[-1])

    same = labels == current
    fwd_vals = fwd_aligned.to_numpy(dtype=float)[same]
    fwd_vals = fwd_vals[~np.isnan(fwd_vals)]
    if len(fwd_vals) == 0:
        bias, win = 0.0, 0.5
    else:
        bias, win = float(np.mean(fwd_vals)), float(np.mean(fwd_vals > 0))

    return RegimeResult(
        current_regime=current,
        n_regimes=k,
        regime_forward_bias=round(bias, 5),
        regime_win_rate=round(win, 4),
        sample_size=int(same.sum()),
    )
