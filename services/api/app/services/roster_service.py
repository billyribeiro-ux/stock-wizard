"""Batch roster validation — forward-test every OHLCV-backtestable scanner across a basket,
blend the out-of-sample results per scanner, and persist a single edge weight each.

This is the system-wide self-grading pass: it pools time-separated validation across many
symbols so the live signal path can weight each scanner by its *blended* out-of-sample edge
rather than a single noisy run. Scanners that need data the event-driven engine can't replay
(options chains, insider/congress flow, earnings/news, market internals, cross-asset aux) are
excluded automatically.
"""

from __future__ import annotations

from engine.backtesting import BacktestConfig, blend_forward_tests, forward_test
from engine.data import validate
from engine.scanners import list_scanner_ids
from engine.schemas import Timeframe

from ..repositories import repo
from .scan_service import (
    _HISTORY_DAYS,
    _HTF,
    _NEEDS_AUX,
    _NEEDS_EARNINGS,
    _NEEDS_FLOW,
    _NEEDS_NEWS,
    _NEEDS_OPTIONS,
    _NEEDS_RISK_RATIOS,
    _NEEDS_UNIVERSE,
    _NEEDS_VOL_TERM,
    _resolve_ohlcv_source,
    _start_for,
)

# Scanners that re-fit a model on every bar — far too slow for a per-bar replay sweep
# (e.g. anomaly_detection fits an estimator each step: minutes per symbol). Their value is
# the live ML, not a cheap backtest, so they're excluded from the roster validation.
_SLOW_FOR_REPLAY: set[str] = {"anomaly_detection"}

# Scanners whose inputs the OHLCV replay can't reconstruct -> not roster-validatable here.
_NOT_BACKTESTABLE: set[str] = (
    _NEEDS_OPTIONS
    | _NEEDS_FLOW
    | _NEEDS_EARNINGS
    | _NEEDS_NEWS
    | _NEEDS_AUX
    | _NEEDS_UNIVERSE
    | _NEEDS_VOL_TERM
    | _NEEDS_RISK_RATIOS
    | _SLOW_FOR_REPLAY
)

DEFAULT_BASKET = ["SPY", "QQQ", "AAPL", "NVDA", "TSLA", "AMZN", "META", "JPM"]


def backtestable_roster() -> list[str]:
    """All registered scanners that run on OHLCV (+ optional HTF) alone."""
    return sorted(s for s in list_scanner_ids() if s not in _NOT_BACKTESTABLE)


async def validate_roster(
    session,
    symbols: list[str] | None = None,
    scanners: list[str] | None = None,
    history: str = "5y",
    timeframe: str = "1d",
    split_frac: float = 0.6,
) -> dict:
    """Forward-test each scanner across the basket, blend, and persist the edge weights.

    Returns a report of per-scanner blended verdicts (also stored via
    ``repo.save_walkforward_edge`` so ``scan_service`` picks them up on the next scan).
    """
    symbols = [s.upper() for s in (symbols or DEFAULT_BASKET)]
    roster = scanners or backtestable_roster()
    tf = Timeframe(timeframe)
    start = _start_for(history) if history in _HISTORY_DAYS else _start_for("5y")
    src = await _resolve_ohlcv_source(session, None)
    cfg = BacktestConfig(min_score=0.35)

    # Fetch each symbol's history once (daily + the HTF that mtf_structure needs).
    data: dict[str, tuple] = {}
    for sym in symbols:
        try:
            ohlcv, _ = validate(src.get_ohlcv(sym, tf, start))
            if len(ohlcv) == 0:
                continue
            htf, _ = validate(src.get_ohlcv(sym, _HTF.get(tf, Timeframe.D1), start))
            data[sym] = (ohlcv, htf)
        except Exception:
            continue

    report: list[dict] = []
    for scanner_id in roster:
        per_symbol = []
        for sym, (ohlcv, htf) in data.items():
            use_htf = htf if scanner_id == "mtf_structure" else None
            try:
                ft = forward_test(
                    scanner_id, ohlcv, htf_ohlcv=use_htf, split_frac=split_frac, config=cfg
                )
            except Exception:
                ft = None
            if ft is not None:
                per_symbol.append((sym, ft))

        blended = blend_forward_tests(scanner_id, per_symbol)
        if blended is None:
            continue
        await repo.save_walkforward_edge(
            session,
            scanner_id,
            promotion=blended.promotion,
            oos_profit_factor=blended.blended_profit_factor,
            edge_weight=blended.edge_weight,
            detail={
                "blend": "roster",
                "n_symbols": blended.n_symbols,
                "total_oos_trades": blended.total_oos_trades,
                "win_rate": blended.blended_win_rate,
                "promote_fraction": blended.promote_fraction,
                "per_symbol": blended.per_symbol,
            },
        )
        report.append(
            {
                "scanner_id": scanner_id,
                "promotion": blended.promotion,
                "edge_weight": blended.edge_weight,
                "blended_profit_factor": blended.blended_profit_factor,
                "blended_win_rate": blended.blended_win_rate,
                "total_oos_trades": blended.total_oos_trades,
                "promote_fraction": blended.promote_fraction,
                "n_symbols": blended.n_symbols,
            }
        )

    report.sort(key=lambda r: r["edge_weight"], reverse=True)
    return {"symbols": symbols, "n_scanners": len(report), "results": report}
