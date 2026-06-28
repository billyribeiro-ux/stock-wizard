"""Multi-scanner ensemble backtest — fuse several scanners into one strategy.

At each bar every scanner in the set runs on the same point-in-time snapshot; their results
are combined by the edge-weighted consensus (``evidence.combine``), and a position is opened
only when the consensus says ``trade``. Retired scanners (edge weight below the floor) are
dropped before voting, so the ensemble trades the *proven* edges, weighted by how well each
has held up out-of-sample. Exit management reuses the standard engine (same stops/targets/
ratchet/time-stop), so results are directly comparable to single-scanner backtests.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..evidence import combine
from ..scanners import build_scanner
from ..scanners.base import ScanContext
from ..schemas import OHLCV, BacktestResult, EquityPoint, Side
from .engine import BacktestConfig, BacktestEngine
from .metrics import compute_metrics

# Mirror the live signal path: an OOS-retired scanner (edge weight < this) is dropped.
_EDGE_FLOOR = 0.5


def backtest_ensemble(
    scanner_ids: list[str],
    ohlcv: OHLCV,
    edge_weights: dict[str, float] | None = None,
    params: dict | None = None,
    config: BacktestConfig | None = None,
    regime_edges_map: dict[str, dict[str, float]] | None = None,
) -> BacktestResult:
    """Run an edge-weighted consensus of ``scanner_ids`` over one symbol's OHLCV.

    When ``regime_edges_map`` is given (scanner -> {regime: weight}), each scanner's vote is
    weighted by its edge in the *current* regime and dropped where it has none — letting a
    momentum scanner (trend) and a mean-reversion scanner (range) cooperate as independent,
    regime-conditional edges rather than one diluting the other."""
    cfg = config or BacktestConfig()
    weights = edge_weights or {}
    regime_map = regime_edges_map or {}
    # Run every candidate each bar; the effective (possibly regime-specific) weight decides
    # whether it votes. All scanners are built once.
    scanners = {s: build_scanner(s, params) for s in scanner_ids}

    def effective_weight(scanner_id: str, regime_kind: str | None) -> float:
        rmap = regime_map.get(scanner_id)
        if rmap and regime_kind in rmap:
            return rmap[regime_kind]
        return weights.get(scanner_id, 1.0)

    eng = BacktestEngine(cfg)
    bars = ohlcv.bars
    from .engine import _State, _years  # reuse engine internals

    state = _State(equity=cfg.starting_equity)
    pos = None
    slip = cfg.slippage_bps / 10_000.0

    for i in range(cfg.warmup, len(bars)):
        bar = bars[i]
        window = OHLCV(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            asset_class=ohlcv.asset_class,
            source=ohlcv.source,
            bars=bars[: i + 1],
        )
        if pos is not None:
            state.bars_in_trade += 1
            pos.bars_held += 1
            exit_px, reason = eng._check_exit(pos, bar, cfg)
            if exit_px is not None:
                eng._close(state, pos, bar.ts, exit_px, reason, slip, cfg)
                pos = None
            else:
                eng._update_excursion(pos, bar)
                eng._ratchet_stop(pos, cfg)

        if pos is None:
            snap = eng.factory.build_snapshot(window)
            ctx = ScanContext(
                symbol=ohlcv.symbol,
                timeframe=ohlcv.timeframe,
                snapshot=snap,
                ohlcv=window,
                as_of=bar.ts,
            )
            from ..scanners.regime_affinity import regime_kind_from_er

            regime_kind = regime_kind_from_er(snap.get("regime.er"))
            results = []
            bar_weights: dict[str, float] = {}
            for sid, sc in scanners.items():
                w = effective_weight(sid, regime_kind)
                if w < _EDGE_FLOOR:  # gated out of this regime
                    continue
                try:
                    results.append(sc.run(ctx))
                    bar_weights[sid] = w
                except Exception:
                    continue
            cons = combine(results, edge_weights=bar_weights)
            if (
                cons.action == "trade"
                and cons.direction in (Side.LONG, Side.SHORT)
                and cons.score >= cfg.min_score
                and (cfg.allow_short or cons.direction == Side.LONG)
            ):
                atr = snap.get("atr.14")
                if atr and atr > 0:
                    pos = eng._open(state, cons.direction, bar, float(atr), slip, cfg)

        state.curve.append(EquityPoint(ts=bar.ts, equity=Decimal(str(round(state.equity, 2)))))

    if pos is not None and bars:
        eng._close(state, pos, bars[-1].ts, float(bars[-1].close), "end_of_data", slip, cfg)

    metrics = compute_metrics(
        state.trades,
        state.curve,
        state.bars_in_trade,
        max(len(bars) - cfg.warmup, 1),
        years=_years(bars),
        starting_equity=cfg.starting_equity,
    )
    return BacktestResult(
        scanner_id="ensemble:" + "+".join(scanner_ids),
        params=params or {},
        universe=[ohlcv.symbol],
        period_start=bars[0].ts.date() if bars else datetime.now().date(),
        period_end=bars[-1].ts.date() if bars else datetime.now().date(),
        trades=state.trades,
        equity_curve=state.curve,
        metrics=metrics,
    )
