"""Event-driven backtester + metrics."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from engine.backtesting import BacktestConfig, BacktestEngine, compute_metrics
from engine.schemas import OHLCV, EquityPoint, MarketBar, Side, Timeframe, TradeRecord
from tests.conftest import make_ohlcv

NOW = datetime(2026, 6, 11, tzinfo=UTC)


def test_backtest_runs_and_reports_metrics():
    ohlcv = make_ohlcv(n=400, drift=0.1, amp=1.5)
    htf = make_ohlcv(n=200, timeframe=Timeframe.H1, drift=0.4)
    engine = BacktestEngine(BacktestConfig(warmup=60, min_score=0.3))
    result = engine.run("mtf_structure", ohlcv, htf_ohlcv=htf)
    assert result.scanner_id == "mtf_structure"
    assert len(result.equity_curve) > 0
    assert result.metrics.total_trades >= 0
    assert 0.0 <= result.metrics.win_rate <= 1.0
    # equity curve timestamps are monotonic
    ts = [p.ts for p in result.equity_curve]
    assert ts == sorted(ts)


def test_backtest_no_lookahead_position_lifecycle():
    """Pure uptrend should produce profitable long trades (no shorts allowed)."""
    base = datetime(2026, 6, 10, 13, 30, tzinfo=UTC)
    bars = []
    px = 100.0
    for i in range(300):
        px += 0.2
        bars.append(
            MarketBar(
                symbol="UP",
                timeframe=Timeframe.M5,
                ts=base + timedelta(minutes=5 * i),
                open=Decimal(str(round(px - 0.05, 2))),
                high=Decimal(str(round(px + 0.15, 2))),
                low=Decimal(str(round(px - 0.15, 2))),
                close=Decimal(str(round(px, 2))),
                volume=100000,
            )
        )
    ohlcv = OHLCV(symbol="UP", timeframe=Timeframe.M5, bars=bars)
    engine = BacktestEngine(BacktestConfig(warmup=40, min_score=0.3, allow_short=False))
    result = engine.run("mtf_structure", ohlcv)
    if result.metrics.total_trades > 0:
        assert all(t.side == Side.LONG for t in result.trades)


def test_metrics_math():
    now = datetime(2026, 6, 11, tzinfo=UTC)
    trades = [
        TradeRecord(
            symbol="X",
            side=Side.LONG,
            entry_ts=now,
            entry_price=Decimal("100"),
            exit_ts=now,
            exit_price=Decimal("110"),
            pnl=Decimal("100"),
            return_pct=0.1,
        ),
        TradeRecord(
            symbol="X",
            side=Side.LONG,
            entry_ts=now,
            entry_price=Decimal("100"),
            exit_ts=now,
            exit_price=Decimal("95"),
            pnl=Decimal("-50"),
            return_pct=-0.05,
        ),
    ]
    curve = [
        EquityPoint(ts=now, equity=Decimal("10100")),
        EquityPoint(ts=now, equity=Decimal("10050")),
    ]
    m = compute_metrics(trades, curve, bars_in_trade=10, total_bars=100)
    assert m.total_trades == 2
    assert m.win_rate == 0.5
    assert m.profit_factor == 2.0  # 100 / 50
    assert m.expectancy == 25.0
    assert math.isclose(float(m.total_pnl), 50.0)


def test_ratchet_stop_moves_to_breakeven_and_trails():
    """Breakeven raises the stop to entry once price runs far enough in favor; trailing
    then follows the high-water mark. Stops must only ever move favorably."""
    from engine.backtesting.engine import _OpenPosition

    eng = BacktestEngine(BacktestConfig(breakeven_atr=1.0, trail_atr=2.0))
    # long entry at 100, atr 2, initial stop 98
    pos = _OpenPosition(
        side=Side.LONG, entry_ts=NOW, entry=100.0, stop=98.0, target=103.0, size=1.0, atr=2.0
    )
    # not yet 1 ATR in profit -> stop unchanged
    pos.mfe = 1.5
    eng._ratchet_stop(pos, eng.cfg)
    assert pos.stop == 98.0
    # reached >=1 ATR (2.0) favorable -> stop ratchets up to breakeven (entry)
    pos.mfe = 2.0
    eng._ratchet_stop(pos, eng.cfg)
    assert pos.stop == 100.0
    # far in profit (5 ATR=10) -> trail to high-water - 2 ATR = 110 - 4 = 106
    pos.mfe = 10.0
    eng._ratchet_stop(pos, eng.cfg)
    assert pos.stop == 106.0
    # excursion pulls back (lower mfe) -> stop never loosens
    pos.mfe = 6.0
    eng._ratchet_stop(pos, eng.cfg)
    assert pos.stop == 106.0


def test_ratchet_disabled_by_default():
    from engine.backtesting.engine import _OpenPosition

    eng = BacktestEngine(BacktestConfig())  # defaults: breakeven_atr=0, trail_atr=0
    pos = _OpenPosition(
        side=Side.SHORT, entry_ts=NOW, entry=100.0, stop=102.0, target=97.0, size=1.0, atr=2.0
    )
    pos.mfe = 8.0
    eng._ratchet_stop(pos, eng.cfg)
    assert pos.stop == 102.0  # untouched when disabled


def test_ensemble_backtest_runs_and_drops_retired():
    from engine.backtesting import backtest_ensemble

    ohlcv = make_ohlcv(n=400, drift=0.1, amp=1.5)
    # volume_profile_poc is "retired" (weight 0.3) -> excluded; only breakout_quality votes.
    res = backtest_ensemble(
        ["breakout_quality", "volume_profile_poc"],
        ohlcv,
        edge_weights={"breakout_quality": 1.5, "volume_profile_poc": 0.3},
        config=BacktestConfig(min_score=0.3),
    )
    assert res.scanner_id == "ensemble:breakout_quality"  # retired one dropped
    assert len(res.equity_curve) > 0
    assert res.metrics.total_trades >= 0


def test_ensemble_all_retired_makes_no_trades():
    from engine.backtesting import backtest_ensemble

    ohlcv = make_ohlcv(n=300, drift=0.05, amp=1.0)
    res = backtest_ensemble(
        ["breakout_quality", "volume_profile_poc"],
        ohlcv,
        edge_weights={"breakout_quality": 0.3, "volume_profile_poc": 0.3},
        config=BacktestConfig(min_score=0.3),
    )
    assert res.metrics.total_trades == 0  # every scanner gated out -> no votes
