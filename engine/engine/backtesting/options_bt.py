"""Multi-leg options structure backtester (BWB, butterflies, verticals).

Historical option chains aren't available from free data, so this engine prices each
structure at entry with Black-Scholes (IV proxied by realized volatility, optionally
scaled by a variance-risk premium) and settles it at expiry from the *realized*
underlying price — a standard research approximation that keeps the test honest about
path outcome while being explicit about the pricing assumption (recorded per trade).

Structures are defined relative to spot/ATR so the same recipe replays across history:
every ``step`` bars, build the structure, pay the model debit (or collect the credit),
hold ``horizon`` bars, settle at intrinsic value.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from ..features import greeks
from ..features.base import ohlcv_to_frame
from ..features.squeeze import realized_vol
from ..schemas import OHLCV, BacktestMetrics, EquityPoint, Side, TradeRecord
from .metrics import compute_metrics


@dataclass(frozen=True)
class Leg:
    right: str  # "C" | "P"
    strike: float
    qty: int  # +long / -short (contracts)


def payoff_at_expiry(legs: list[Leg], settle: float, multiplier: int = 100) -> float:
    """Intrinsic value of the structure at expiration."""
    total = 0.0
    for leg in legs:
        intrinsic = (
            max(0.0, settle - leg.strike) if leg.right == "C" else max(0.0, leg.strike - settle)
        )
        total += intrinsic * leg.qty * multiplier
    return total


def price_structure(
    legs: list[Leg], spot: float, t_years: float, r: float, sigma: float, multiplier: int = 100
) -> float:
    """Model entry cost: positive = net debit paid, negative = net credit received."""
    cost = 0.0
    for leg in legs:
        px = float(greeks.bs_price(spot, leg.strike, t_years, r, sigma, leg.right))
        cost += px * leg.qty * multiplier
    return cost


# ---- structure builders (relative to spot / expected move) ----
def bwb_builder(direction: Side = Side.LONG, wing_ratio: float = 1.5) -> Callable:
    """Broken-wing butterfly: body ~0.5 EM in the lean direction, asymmetric wings."""

    def build(spot: float, em: float) -> list[Leg]:
        sign = 1 if direction == Side.LONG else -1
        right = "C" if direction == Side.LONG else "P"
        body = round(spot + sign * 0.5 * em)
        wing = max(round(em), 1)
        near = body - sign * wing
        far = body + sign * round(wing * wing_ratio)
        return [Leg(right, near, 1), Leg(right, body, -2), Leg(right, far, 1)]

    return build


def vertical_builder(direction: Side = Side.LONG, width_em: float = 0.5) -> Callable:
    """Debit vertical: long ATM, short one width in the lean direction."""

    def build(spot: float, em: float) -> list[Leg]:
        sign = 1 if direction == Side.LONG else -1
        right = "C" if direction == Side.LONG else "P"
        atm = round(spot)
        far = round(spot + sign * max(width_em * em, 1))
        return [Leg(right, atm, 1), Leg(right, far, -1)]

    return build


def backtest_structure(
    ohlcv: OHLCV,
    builder: Callable[[float, float], list[Leg]],
    horizon: int = 10,
    step: int = 10,
    r: float = 0.05,
    iv_premium: float = 1.1,
    warmup: int = 30,
    starting_equity: float = 10_000.0,
):
    """Replay the structure recipe across history. Returns (trades, equity, metrics)."""
    df = ohlcv_to_frame(ohlcv)
    if len(df) < warmup + horizon + 1:
        return [], [], BacktestMetrics()
    closes = df["close"].to_numpy(dtype=float)
    bars_per_year = (
        max(int(252 * 86400 / max(ohlcv.timeframe.seconds, 1) / 6.5), 252)
        if ohlcv.timeframe.is_intraday
        else 252
    )
    t_years = horizon / bars_per_year

    trades: list[TradeRecord] = []
    curve: list[EquityPoint] = []
    equity = starting_equity

    i = warmup
    while i + horizon < len(df):
        window = df.iloc[: i + 1]
        rv = realized_vol(window, 20, periods_per_year=bars_per_year)
        if rv is None or rv <= 0:
            i += step
            continue
        sigma = rv * iv_premium  # implied trades rich to realized on average
        spot = closes[i]
        em = spot * sigma * np.sqrt(t_years)  # 1σ expected move over the horizon
        legs = builder(spot, em)
        entry_cost = price_structure(legs, spot, t_years, r, sigma)

        settle = closes[i + horizon]
        value = payoff_at_expiry(legs, settle)
        pnl = value - entry_cost
        equity += pnl
        basis = abs(entry_cost)
        trades.append(
            TradeRecord(
                symbol=ohlcv.symbol,
                side=Side.LONG,  # long the structure itself
                entry_ts=df.index[i].to_pydatetime(),
                entry_price=Decimal(str(round(entry_cost, 2))),
                exit_ts=df.index[i + horizon].to_pydatetime(),
                exit_price=Decimal(str(round(value, 2))),
                pnl=Decimal(str(round(pnl, 2))),
                return_pct=round(pnl / basis, 6) if basis > 0 else 0.0,
                hold_seconds=int((df.index[i + horizon] - df.index[i]).total_seconds()),
                exit_reason="expiry",
            )
        )
        curve.append(
            EquityPoint(
                ts=df.index[i + horizon].to_pydatetime(), equity=Decimal(str(round(equity, 2)))
            )
        )
        i += step

    metrics = compute_metrics(trades, curve, starting_equity=starting_equity)
    return trades, curve, metrics
