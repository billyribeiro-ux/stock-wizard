"""Options-chain derived metrics: expected move, max pain, OI clusters, skew,
aggregate charm/vanna pressure. All operate on the canonical OptionChain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from ..schemas import OptionChain, OptionRight
from . import greeks


def years_to_expiry(as_of: datetime, expiry: date) -> float:
    """0DTE-aware time to expiry in years (floored to avoid greeks blow-ups)."""
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    days = (expiry - as_of.date()).days
    if days <= 0:
        from common.timeutils import year_fraction_to_close

        return year_fraction_to_close(as_of)
    return max(days / 365.0, 1e-6)


@dataclass(frozen=True)
class ExpectedMove:
    straddle: float  # ATM straddle mid (≈ 1σ expected move in $)
    iv_based: float  # S·σ·√T
    atm_strike: float
    atm_iv: float


def expected_move(
    chain: OptionChain, t_years: float, expiry: date | None = None
) -> ExpectedMove | None:
    target = expiry or (chain.expiries[0] if chain.expiries else None)
    if target is None:
        return None
    spot = float(chain.spot)
    contracts = chain.for_expiry(target)
    if not contracts or spot <= 0:
        return None
    atm = min(contracts, key=lambda c: abs(float(c.strike) - spot))
    atm_strike = float(atm.strike)
    calls = [c for c in contracts if c.right == OptionRight.CALL and float(c.strike) == atm_strike]
    puts = [c for c in contracts if c.right == OptionRight.PUT and float(c.strike) == atm_strike]
    straddle = 0.0
    for leg in calls[:1] + puts[:1]:
        mid = leg.mid
        if mid is not None:
            straddle += float(mid)
    atm_iv = atm.iv or (atm.greeks.iv if atm.greeks else 0.0) or 0.0
    iv_based = spot * atm_iv * np.sqrt(t_years) if atm_iv > 0 else 0.0
    return ExpectedMove(
        straddle=straddle, iv_based=float(iv_based), atm_strike=atm_strike, atm_iv=atm_iv
    )


def max_pain(chain: OptionChain, expiry: date | None = None) -> float | None:
    """Strike that minimizes total in-the-money payoff to option holders at expiry."""
    target = expiry or (chain.expiries[0] if chain.expiries else None)
    if target is None:
        return None
    contracts = chain.for_expiry(target)
    strikes = sorted({float(c.strike) for c in contracts})
    if not strikes:
        return None
    best_strike, best_pain = None, float("inf")
    for s in strikes:
        pain = 0.0
        for c in contracts:
            k = float(c.strike)
            if c.right == OptionRight.CALL and s > k:
                pain += (s - k) * c.open_interest
            elif c.right == OptionRight.PUT and s < k:
                pain += (k - s) * c.open_interest
        if pain < best_pain:
            best_pain, best_strike = pain, s
    return best_strike


def oi_clusters(
    chain: OptionChain, expiry: date | None = None, top: int = 5
) -> list[tuple[float, int]]:
    target = expiry or (chain.expiries[0] if chain.expiries else None)
    if target is None:
        return []
    by_strike: dict[float, int] = {}
    for c in chain.for_expiry(target):
        by_strike[float(c.strike)] = by_strike.get(float(c.strike), 0) + c.open_interest
    return sorted(by_strike.items(), key=lambda kv: kv[1], reverse=True)[:top]


@dataclass(frozen=True)
class Skew:
    put_iv: float
    call_iv: float
    skew: float  # put_iv - call_iv (positive = downside fear)
    put_strike: float
    call_strike: float


def put_call_skew(
    chain: OptionChain, expiry: date | None = None, offset_pct: float = 0.05
) -> Skew | None:
    """IV of an OTM put vs OTM call ~offset_pct away from spot (25-delta proxy)."""
    target = expiry or (chain.expiries[0] if chain.expiries else None)
    if target is None:
        return None
    spot = float(chain.spot)
    if spot <= 0:
        return None
    put_target, call_target = spot * (1 - offset_pct), spot * (1 + offset_pct)
    puts = [c for c in chain.for_expiry(target) if c.right == OptionRight.PUT and c.iv]
    calls = [c for c in chain.for_expiry(target) if c.right == OptionRight.CALL and c.iv]
    if not puts or not calls:
        return None
    p = min(puts, key=lambda c: abs(float(c.strike) - put_target))
    c_ = min(calls, key=lambda c: abs(float(c.strike) - call_target))
    p_iv, c_iv = p.iv, c_.iv
    if p_iv is None or c_iv is None:  # guaranteed by the `c.iv` filter above; narrows for mypy
        return None
    return Skew(
        put_iv=p_iv,
        call_iv=c_iv,
        skew=p_iv - c_iv,
        put_strike=float(p.strike),
        call_strike=float(c_.strike),
    )


@dataclass(frozen=True)
class GreekPressure:
    charm: float
    vanna: float
    meta: dict = field(default_factory=dict)


def aggregate_charm_vanna(
    chain: OptionChain, t_years: float, expiry: date | None = None
) -> GreekPressure | None:
    """OI-weighted dealer charm/vanna pressure (calls +, puts −)."""
    target = expiry or (chain.expiries[0] if chain.expiries else None)
    if target is None:
        return None
    spot, r = float(chain.spot), chain.risk_free_rate
    total_charm = total_vanna = 0.0
    for c in chain.for_expiry(target):
        sigma = c.iv or (c.greeks.iv if c.greeks else 0.0)
        if not sigma or c.open_interest <= 0:
            continue
        sign = 1.0 if c.right == OptionRight.CALL else -1.0
        k = float(c.strike)
        total_charm += float(greeks.charm(spot, k, t_years, r, sigma)) * c.open_interest * sign
        total_vanna += float(greeks.vanna(spot, k, t_years, r, sigma)) * c.open_interest * sign
    return GreekPressure(charm=total_charm, vanna=total_vanna)
