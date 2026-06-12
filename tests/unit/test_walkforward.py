"""Walk-forward validation, Monte-Carlo stress, and forward (paper) testing."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from engine.backtesting import forward_test, monte_carlo, walk_forward
from engine.backtesting.engine import BacktestConfig
from engine.schemas import Side, Timeframe, TradeRecord
from tests.conftest import make_ohlcv

CFG = BacktestConfig(warmup=40, min_score=0.3)


def test_forward_test_splits_and_decides():
    ohlcv = make_ohlcv(n=600, drift=0.08, amp=1.5)
    htf = make_ohlcv(n=300, timeframe=Timeframe.H1, drift=0.3)
    ft = forward_test("mtf_structure", ohlcv, htf_ohlcv=htf, split_frac=0.6, config=CFG)
    assert ft is not None
    assert ft.promotion in {"promote", "keep_testing", "retire"}
    assert set(ft.drift) >= {"win_rate", "profit_factor", "expectancy"}
    assert ft.out_of_sample is not None
    assert "total_trades" in ft.forward


def test_forward_test_insufficient_history():
    assert forward_test("mtf_structure", make_ohlcv(n=100), config=CFG) is None


def test_walk_forward_splits():
    ohlcv = make_ohlcv(n=600, drift=0.05, amp=1.5)
    splits = walk_forward("volume_profile_poc", ohlcv, n_splits=3, config=CFG)
    assert len(splits) == 3
    for s in splits:
        assert "metrics" in s and "period_start" in s


def test_monte_carlo_distribution():
    now = datetime(2026, 6, 11, tzinfo=UTC)
    trades = [
        TradeRecord(
            symbol="X",
            side=Side.LONG,
            entry_ts=now,
            entry_price=Decimal("100"),
            exit_ts=now,
            exit_price=Decimal("101"),
            pnl=Decimal(str(p)),
        )
        for p in [100, -50, 80, -40, 120, -30, 90, -60, 110, -20]
    ]
    mc = monte_carlo(trades, n_sims=500)
    assert mc is not None
    assert 0.0 <= mc.prob_profit <= 1.0
    assert mc.p05_return <= mc.median_return <= mc.p95_return
    assert mc.worst_max_dd >= mc.median_max_dd


def test_monte_carlo_too_few_trades():
    assert monte_carlo([], n_sims=100) is None
