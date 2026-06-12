"""Portfolio backtester — run a scanner strategy across a basket of symbols.

Capital is split into equal sleeves (one per symbol); each sleeve runs the standard
event-driven engine independently, then the sleeves' equity curves are aligned on the
union of timestamps (forward-filled) and summed into one portfolio curve with combined
trades and metrics. This is the "independent sleeves" model — correlation effects show
up in the combined drawdown, which is the number that matters.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import OHLCV, BacktestResult, EquityPoint
from .engine import BacktestConfig, BacktestEngine
from .metrics import compute_metrics


def backtest_portfolio(
    scanner_id: str,
    ohlcv_map: dict[str, OHLCV],
    params: dict | None = None,
    htf_map: dict[str, OHLCV] | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult | None:
    if not ohlcv_map:
        return None
    cfg = config or BacktestConfig()
    n = len(ohlcv_map)
    sleeve_cfg = BacktestConfig(**{**cfg.__dict__, "starting_equity": cfg.starting_equity / n})

    engine = BacktestEngine(sleeve_cfg)
    sleeve_curves: list[list[EquityPoint]] = []
    all_trades = []
    period_start = None
    period_end = None

    for symbol, ohlcv in ohlcv_map.items():
        htf = (htf_map or {}).get(symbol)
        res = engine.run(scanner_id, ohlcv, params=params, htf_ohlcv=htf)
        for t in res.trades:
            t.symbol = symbol
        all_trades.extend(res.trades)
        if res.equity_curve:
            sleeve_curves.append(res.equity_curve)
        if res.trades or res.equity_curve:
            period_start = min(period_start or res.period_start, res.period_start)
            period_end = max(period_end or res.period_end, res.period_end)

    if not sleeve_curves:
        return None

    # Merge sleeves: union of timestamps, forward-fill each sleeve, sum.
    all_ts = sorted({p.ts for curve in sleeve_curves for p in curve})
    merged: list[EquityPoint] = []
    cursors = [0] * len(sleeve_curves)
    lasts = [float(curve[0].equity) for curve in sleeve_curves]
    for ts in all_ts:
        total = 0.0
        for k, curve in enumerate(sleeve_curves):
            while cursors[k] < len(curve) and curve[cursors[k]].ts <= ts:
                lasts[k] = float(curve[cursors[k]].equity)
                cursors[k] += 1
            total += lasts[k]
        merged.append(EquityPoint(ts=ts, equity=Decimal(str(round(total, 2)))))

    all_trades.sort(key=lambda t: t.entry_ts)
    years = 0.0
    if len(all_ts) >= 2:
        years = (all_ts[-1] - all_ts[0]).total_seconds() / (365.25 * 24 * 3600)
    metrics = compute_metrics(all_trades, merged, years=years, starting_equity=cfg.starting_equity)
    return BacktestResult(
        scanner_id=scanner_id,
        params=params or {},
        universe=sorted(ohlcv_map),
        period_start=period_start,
        period_end=period_end,
        trades=all_trades,
        equity_curve=merged,
        metrics=metrics,
    )
