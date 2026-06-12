"""Backtest performance metrics computed from closed trades + an equity curve."""

from __future__ import annotations

import math
from decimal import Decimal

from ..schemas import BacktestMetrics, EquityPoint, TradeRecord


def _sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    return (mean / std) * math.sqrt(len(returns)) if std > 0 else 0.0


def _sortino(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("inf") if mean > 0 else 0.0
    dvar = sum(r**2 for r in downside) / len(downside)
    dstd = math.sqrt(dvar)
    return (mean / dstd) * math.sqrt(len(returns)) if dstd > 0 else 0.0


def max_drawdown(equity: list[EquityPoint]) -> float:
    peak = -math.inf
    mdd = 0.0
    for pt in equity:
        eq = float(pt.equity)
        peak = max(peak, eq)
        if peak > 0:
            mdd = max(mdd, (peak - eq) / peak)
    return mdd


def compute_metrics(
    trades: list[TradeRecord],
    equity: list[EquityPoint],
    bars_in_trade: int = 0,
    total_bars: int = 0,
    years: float = 0.0,
    starting_equity: float = 10_000.0,
) -> BacktestMetrics:
    closed = [t for t in trades if t.pnl is not None]
    n = len(closed)
    if n == 0:
        return BacktestMetrics()

    pnls = [float(t.pnl) for t in closed]
    rets = [t.return_pct for t in closed if t.return_pct is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    win_rate = len(wins) / n
    profit_factor = (
        (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win else 0.0)
    )
    expectancy = sum(pnls) / n
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    avg_rr = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    mdd = max_drawdown(equity)
    total_pnl = sum(pnls)
    recovery = (total_pnl / (mdd * starting_equity)) if mdd > 0 else 0.0

    cagr = 0.0
    if years > 0 and equity:
        end_eq = float(equity[-1].equity)
        if starting_equity > 0 and end_eq > 0:
            cagr = (end_eq / starting_equity) ** (1 / years) - 1

    exposure = (bars_in_trade / total_bars) if total_bars > 0 else 0.0

    return BacktestMetrics(
        total_trades=n,
        win_rate=round(win_rate, 4),
        profit_factor=round(profit_factor, 4),
        expectancy=round(expectancy, 4),
        total_pnl=Decimal(str(round(total_pnl, 4))),
        cagr=round(cagr, 4),
        sharpe=round(_sharpe(rets), 4),
        sortino=round(_sortino(rets), 4) if _sortino(rets) != float("inf") else 0.0,
        max_drawdown=round(mdd, 4),
        recovery_factor=round(recovery, 4),
        avg_win=round(avg_win, 4),
        avg_loss=round(avg_loss, 4),
        avg_rr=round(avg_rr, 4),
        exposure=round(exposure, 4),
    )
