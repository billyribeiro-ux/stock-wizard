"""Absorption Ratio — a systemic-risk / market-fragility measure (Kritzman & Lo, 2010,
"Principal Components as a Measure of Systemic Risk").

The Absorption Ratio is the fraction of the universe's total return variance explained
by its top few principal components (eigenvectors of the return covariance matrix). When
a handful of factors absorb most of the variance the market is *tightly coupled* — small
shocks propagate everywhere — which historically precedes drawdowns. A sharp *increase*
in AR (Kritzman's standardized shift) is the actionable fragility warning.

This is the blueprint's "linear algebra: eigenvectors for regime and risk decomposition"
done properly — institutional desks run exactly this.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..features.base import ohlcv_to_frame
from ..schemas import OHLCV


@dataclass
class AbsorptionResult:
    absorption_ratio: float  # share of variance in the top-k eigenvectors (0..1)
    n_components: int  # k
    n_assets: int
    standardized_shift: float  # (short-window AR - long mean) / long std  (Kritzman)
    elevated: bool  # shift > +1σ -> fragility warning
    eigen_share: list[float] = field(default_factory=list)  # variance share per component
    series_tail: list[float] = field(default_factory=list)  # recent AR history


def _returns_matrix(universe: dict[str, OHLCV], min_obs: int) -> pd.DataFrame | None:
    cols = {}
    for sym, ohlcv in universe.items():
        df = ohlcv_to_frame(ohlcv)
        if len(df) >= 3:
            cols[sym] = df["close"]
    if len(cols) < 5:
        return None
    prices = pd.DataFrame(cols).sort_index()
    rets = prices.pct_change().dropna(how="any")
    return rets if len(rets) >= min_obs else None


def _absorption_at(window_rets: np.ndarray, frac: float) -> tuple[float, np.ndarray]:
    """AR over one window: top-k eigenvalue share of the correlation matrix."""
    # standardize columns -> correlation-matrix PCA (scale-free across assets)
    std = window_rets.std(axis=0)
    std[std == 0] = 1.0
    z = (window_rets - window_rets.mean(axis=0)) / std
    cov = np.cov(z, rowvar=False)
    eigvals = np.linalg.eigvalsh(cov)  # ascending, real (symmetric)
    eigvals = np.clip(eigvals[::-1], 0, None)  # descending, non-negative
    total = eigvals.sum()
    if total <= 0:
        return 0.0, eigvals
    k = max(1, round(frac * len(eigvals)))
    return float(eigvals[:k].sum() / total), eigvals


def compute_absorption(
    universe: dict[str, OHLCV],
    window: int = 60,
    frac: float = 0.2,
    short_window: int = 15,
) -> AbsorptionResult | None:
    rets = _returns_matrix(universe, min_obs=window + short_window + 5)
    if rets is None:
        return None
    arr = rets.to_numpy(dtype=float)
    n_assets = arr.shape[1]

    # rolling AR series
    series: list[float] = []
    last_eig = np.array([])
    for t in range(window, len(arr) + 1):
        ar, eig = _absorption_at(arr[t - window : t], frac)
        series.append(ar)
        last_eig = eig
    if not series:
        return None
    ar_series = np.asarray(series)
    long_mean = float(ar_series.mean())
    long_std = float(ar_series.std()) or 1e-9
    short_mean = float(ar_series[-short_window:].mean())
    shift = (short_mean - long_mean) / long_std

    total = last_eig.sum() or 1.0
    return AbsorptionResult(
        absorption_ratio=round(float(ar_series[-1]), 4),
        n_components=max(1, round(frac * n_assets)),
        n_assets=n_assets,
        standardized_shift=round(float(shift), 3),
        elevated=bool(shift > 1.0),
        eigen_share=[round(float(e / total), 4) for e in last_eig[:5]],
        series_tail=[round(float(x), 4) for x in ar_series[-30:]],
    )
