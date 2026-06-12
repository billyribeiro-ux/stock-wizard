"""Multi-leg options structure + portfolio backtesters."""

from __future__ import annotations

import pytest

from engine.backtesting import (
    BacktestConfig,
    Leg,
    backtest_portfolio,
    backtest_structure,
    bwb_builder,
    payoff_at_expiry,
    price_structure,
    vertical_builder,
)
from engine.schemas import Side, Timeframe
from tests.conftest import make_ohlcv


# ---- payoff math (golden) ----
def test_call_vertical_payoff_at_expiry():
    legs = [Leg("C", 100, 1), Leg("C", 105, -1)]  # 100/105 call debit vertical
    assert payoff_at_expiry(legs, 110) == pytest.approx(5 * 100)  # capped at width
    assert payoff_at_expiry(legs, 103) == pytest.approx(3 * 100)
    assert payoff_at_expiry(legs, 95) == 0.0


def test_butterfly_payoff_peaks_at_body():
    legs = [Leg("C", 95, 1), Leg("C", 100, -2), Leg("C", 105, 1)]
    assert payoff_at_expiry(legs, 100) == pytest.approx(5 * 100)  # max at the body
    assert payoff_at_expiry(legs, 90) == 0.0
    assert payoff_at_expiry(legs, 110) == pytest.approx(0.0)  # symmetric wings cancel


def test_price_structure_debit_positive_for_long_vertical():
    legs = [Leg("C", 100, 1), Leg("C", 105, -1)]
    cost = price_structure(legs, spot=100, t_years=30 / 365, r=0.05, sigma=0.2)
    assert 0 < cost < 5 * 100  # debit below max payoff


def test_bwb_builder_shape():
    legs = bwb_builder(Side.LONG)(spot=500.0, em=10.0)
    assert len(legs) == 3
    assert sum(leg.qty for leg in legs) == 0  # 1 / -2 / 1
    assert all(leg.right == "C" for leg in legs)


# ---- structure backtest ----
def test_backtest_structure_runs():
    ohlcv = make_ohlcv(n=400, drift=0.05, amp=2.0, timeframe=Timeframe.D1)
    trades, _curve, metrics = backtest_structure(
        ohlcv, vertical_builder(Side.LONG), horizon=10, step=15
    )
    assert len(trades) > 5
    assert metrics.total_trades == len(trades)
    for t in trades:
        assert t.exit_reason == "expiry"
        assert t.pnl is not None


def test_backtest_structure_insufficient_history():
    trades, _curve, metrics = backtest_structure(make_ohlcv(n=20), bwb_builder())
    assert trades == [] and metrics.total_trades == 0


# ---- portfolio ----
def test_portfolio_combines_sleeves():
    ohlcv_map = {
        "AAA": make_ohlcv(symbol="AAA", n=300, drift=0.1, amp=1.5),
        "BBB": make_ohlcv(symbol="BBB", n=300, drift=-0.05, amp=2.0, start_px=50),
    }
    res = backtest_portfolio(
        "mtf_structure", ohlcv_map, config=BacktestConfig(warmup=40, min_score=0.3)
    )
    assert res is not None
    assert res.universe == ["AAA", "BBB"]
    assert len(res.equity_curve) > 0
    # merged curve starts near total starting equity
    assert float(res.equity_curve[0].equity) == pytest.approx(10_000.0, rel=0.05)
    # all trades are stamped with their symbol
    assert {t.symbol for t in res.trades} <= {"AAA", "BBB"}


def test_portfolio_empty_map():
    assert backtest_portfolio("mtf_structure", {}) is None
