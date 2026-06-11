"""Gamma Exposure (GEX) by strike, gamma walls, and the gamma-flip / zero-gamma level.

Dealer-gamma convention (``DEALER_LONG_CALLS``, the common one): calls contribute
positive gamma, puts negative, to dealer exposure. Per strike:

    GEX(K) = gamma(K) · OI(K) · multiplier · S² · 0.01 · sign(right)

interpreted as the $ change in dealer delta per 1% move in spot. Total > 0 ⇒
positive-gamma regime (dealers dampen vol, mean-reversion); < 0 ⇒ negative-gamma
(dealers chase, momentum). The **flip** is the spot where the *total* gamma profile —
recomputed across a spot grid with IVs held fixed — crosses zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from ..schemas import GexConvention, OptionChain, OptionRight
from . import greeks


@dataclass(frozen=True)
class StrikeGex:
    strike: float
    call_gex: float
    put_gex: float

    @property
    def net(self) -> float:
        return self.call_gex + self.put_gex

    @property
    def total_abs(self) -> float:
        return abs(self.call_gex) + abs(self.put_gex)


@dataclass(frozen=True)
class GexProfile:
    spot: float
    expiry: date
    total_gex: float
    per_strike: list[StrikeGex]
    call_wall: float | None
    put_wall: float | None
    flip: float | None
    regime: str  # "positive" | "negative"
    degraded: bool = False
    meta: dict = field(default_factory=dict)


def _sigma_for(contract, spot: float, t: float, r: float) -> float | None:
    """Use the contract's IV if present, else solve it from the mid price."""
    if contract.greeks is not None and contract.greeks.iv > 0:
        return contract.greeks.iv
    if contract.iv is not None and contract.iv > 0:
        return contract.iv
    mid = contract.mid
    if mid is None:
        return None
    return greeks.implied_vol(float(mid), spot, float(contract.strike), t, r, contract.right.value)


def _total_gex_at(
    spot: float,
    strikes: np.ndarray,
    ois: np.ndarray,
    sigmas: np.ndarray,
    signs: np.ndarray,
    mult: np.ndarray,
    t: float,
    r: float,
) -> float:
    g = greeks.gamma(spot, strikes, t, r, sigmas)
    gex = g * ois * mult * (spot**2) * 0.01 * signs
    return float(np.sum(gex))


def compute_gex_profile(
    chain: OptionChain,
    t_years: float,
    expiry: date | None = None,
    convention: GexConvention = GexConvention.DEALER_LONG_CALLS,
    flip_grid: int = 121,
) -> GexProfile | None:
    """Build the GEX profile for one expiry. ``t_years`` = time to that expiry."""
    spot = float(chain.spot)
    r = chain.risk_free_rate
    target = expiry or (chain.expiries[0] if chain.expiries else None)
    if target is None or spot <= 0:
        return None

    contracts = [c for c in chain.for_expiry(target) if c.open_interest > 0]
    if not contracts:
        return None

    strikes_l, ois_l, sigmas_l, signs_l, mult_l = [], [], [], [], []
    by_strike: dict[float, list[float]] = {}
    skipped = 0
    for c in contracts:
        sigma = _sigma_for(c, spot, t_years, r)
        if sigma is None or sigma <= 0:
            skipped += 1
            continue
        sign = 1.0
        if convention == GexConvention.DEALER_LONG_CALLS:
            sign = 1.0 if c.right == OptionRight.CALL else -1.0
        g = float(greeks.gamma(spot, float(c.strike), t_years, r, sigma))
        gex = g * c.open_interest * c.multiplier * (spot**2) * 0.01 * sign
        k = float(c.strike)
        slot = by_strike.setdefault(k, [0.0, 0.0])
        if c.right == OptionRight.CALL:
            slot[0] += gex
        else:
            slot[1] += gex
        strikes_l.append(k)
        ois_l.append(float(c.open_interest))
        sigmas_l.append(sigma)
        signs_l.append(sign)
        mult_l.append(float(c.multiplier))

    if not by_strike:
        return None

    per_strike = [
        StrikeGex(strike=k, call_gex=v[0], put_gex=v[1]) for k, v in sorted(by_strike.items())
    ]
    total = sum(s.net for s in per_strike)

    # Walls: largest |net GEX| strike above (call wall) / below (put wall) spot.
    above = [s for s in per_strike if s.strike >= spot]
    below = [s for s in per_strike if s.strike < spot]
    call_wall = max(above, key=lambda s: abs(s.net)).strike if above else None
    put_wall = max(below, key=lambda s: abs(s.net)).strike if below else None

    # Flip / zero-gamma: scan total gamma profile across a spot grid, find sign change
    # nearest to current spot.
    strikes = np.array(strikes_l)
    ois = np.array(ois_l)
    sigmas = np.array(sigmas_l)
    signs = np.array(signs_l)
    mult = np.array(mult_l)
    lo, hi = float(strikes.min()), float(strikes.max())
    grid = np.linspace(lo, hi, flip_grid)
    profile = np.array(
        [_total_gex_at(g, strikes, ois, sigmas, signs, mult, t_years, r) for g in grid]
    )
    flip = _nearest_zero_crossing(grid, profile, spot)

    regime = "positive" if total >= 0 else "negative"
    degraded = chain.degraded or skipped > len(contracts) // 2

    return GexProfile(
        spot=spot,
        expiry=target,
        total_gex=total,
        per_strike=per_strike,
        call_wall=call_wall,
        put_wall=put_wall,
        flip=flip,
        regime=regime,
        degraded=degraded,
        meta={"n_strikes": len(per_strike), "skipped_contracts": skipped},
    )


def _nearest_zero_crossing(grid: np.ndarray, profile: np.ndarray, spot: float) -> float | None:
    """Linear-interpolated zero crossing of `profile` over `grid`, nearest to `spot`."""
    crossings: list[float] = []
    for i in range(len(grid) - 1):
        y0, y1 = profile[i], profile[i + 1]
        if y0 == 0.0:
            crossings.append(float(grid[i]))
        elif y0 * y1 < 0:
            x0, x1 = grid[i], grid[i + 1]
            crossings.append(float(x0 - y0 * (x1 - x0) / (y1 - y0)))
    if not crossings:
        return None
    return min(crossings, key=lambda x: abs(x - spot))
