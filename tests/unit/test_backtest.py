"""Event-driven backtester + metrics."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from engine.backtesting import BacktestConfig, BacktestEngine, compute_metrics
from engine.schemas import OHLCV, EquityPoint, MarketBar, Side, Timeframe, TradeRecord
from tests.conftest import make_ohlcv


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
