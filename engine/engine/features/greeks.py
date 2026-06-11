"""Black-Scholes greeks + implied-volatility solver (closed form, scipy-backed).

We compute greeks ourselves because yfinance does not supply them. Gamma is the
critical input to GEX, so it is implemented transparently and pinned by a golden test.
Works on scalars or numpy arrays. Time ``t`` is in years; ``r`` annualized; ``sigma``
annualized. Guards against ``t -> 0`` and ``sigma <= 0`` (0DTE near the close).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

_MIN_T = 1e-6
_MIN_SIGMA = 1e-6


def _d1_d2(s, k, t, r, sigma):
    s = np.asarray(s, dtype=float)
    k = np.asarray(k, dtype=float)
    t = np.maximum(np.asarray(t, dtype=float), _MIN_T)
    sigma = np.maximum(np.asarray(sigma, dtype=float), _MIN_SIGMA)
    d1 = (np.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    return d1, d2, t, sigma


def gamma(s, k, t, r, sigma):
    """dDelta/dSpot. Identical for calls and puts: N'(d1) / (S·σ·√T)."""
    s = np.asarray(s, dtype=float)
    d1, _, t, sigma = _d1_d2(s, k, t, r, sigma)
    return norm.pdf(d1) / (s * sigma * np.sqrt(t))


def delta(s, k, t, r, sigma, right: str = "C"):
    d1, _, _, _ = _d1_d2(s, k, t, r, sigma)
    if right.upper().startswith("C"):
        return norm.cdf(d1)
    return norm.cdf(d1) - 1.0


def vega(s, k, t, r, sigma):
    """Per 1.00 change in vol (divide by 100 for per-1%)."""
    s = np.asarray(s, dtype=float)
    d1, _, t, _ = _d1_d2(s, k, t, r, sigma)
    return s * norm.pdf(d1) * np.sqrt(t)


def theta(s, k, t, r, sigma, right: str = "C"):
    """Per year (divide by 365 for per-calendar-day)."""
    s = np.asarray(s, dtype=float)
    k = np.asarray(k, dtype=float)
    d1, d2, t, sigma = _d1_d2(s, k, t, r, sigma)
    term1 = -(s * norm.pdf(d1) * sigma) / (2.0 * np.sqrt(t))
    if right.upper().startswith("C"):
        term2 = -r * k * np.exp(-r * t) * norm.cdf(d2)
    else:
        term2 = r * k * np.exp(-r * t) * norm.cdf(-d2)
    return term1 + term2


def rho(s, k, t, r, sigma, right: str = "C"):
    k = np.asarray(k, dtype=float)
    _, d2, t, _ = _d1_d2(s, k, t, r, sigma)
    if right.upper().startswith("C"):
        return k * t * np.exp(-r * t) * norm.cdf(d2)
    return -k * t * np.exp(-r * t) * norm.cdf(-d2)


def bs_price(s, k, t, r, sigma, right: str = "C"):
    s = np.asarray(s, dtype=float)
    k = np.asarray(k, dtype=float)
    d1, d2, t, _ = _d1_d2(s, k, t, r, sigma)
    if right.upper().startswith("C"):
        return s * norm.cdf(d1) - k * np.exp(-r * t) * norm.cdf(d2)
    return k * np.exp(-r * t) * norm.cdf(-d2) - s * norm.cdf(-d1)


def implied_vol(
    price: float,
    s: float,
    k: float,
    t: float,
    r: float,
    right: str = "C",
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float | None:
    """Solve IV from a market price. Newton-Raphson with a bisection fallback."""
    if price is None or price <= 0 or s <= 0 or k <= 0:
        return None
    t = max(t, _MIN_T)

    # Intrinsic-value sanity floor.
    intrinsic = max(0.0, s - k) if right.upper().startswith("C") else max(0.0, k - s)
    if price < intrinsic - 1e-6:
        return None

    sigma = 0.5
    for _ in range(max_iter):
        diff = float(bs_price(s, k, t, r, sigma, right)) - price
        if abs(diff) < tol:
            return float(sigma)
        v = float(vega(s, k, t, r, sigma))
        if v < 1e-8:
            break
        sigma -= diff / v
        if sigma <= _MIN_SIGMA or sigma > 10:
            break

    # Bisection fallback on [1e-4, 10].
    lo, hi = 1e-4, 10.0
    plo = float(bs_price(s, k, t, r, lo, right)) - price
    phi = float(bs_price(s, k, t, r, hi, right)) - price
    if plo * phi > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        pm = float(bs_price(s, k, t, r, mid, right)) - price
        if abs(pm) < tol:
            return float(mid)
        if plo * pm < 0:
            hi = mid
        else:
            lo, plo = mid, pm
    return float(0.5 * (lo + hi))
