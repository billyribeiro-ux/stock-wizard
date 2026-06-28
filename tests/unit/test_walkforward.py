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


def test_blend_forward_tests_pools_across_symbols():
    from engine.backtesting import blend_forward_tests

    a = make_ohlcv(n=600, drift=0.08, amp=1.5)
    b = make_ohlcv(n=600, drift=0.06, amp=2.0, start_px=50.0)
    fts = []
    for sym, o in [("A", a), ("B", b)]:
        ft = forward_test("volume_profile_poc", o, split_frac=0.6, config=CFG)
        if ft is not None:
            fts.append((sym, ft))
    assert fts, "expected at least one forward test to run"

    blended = blend_forward_tests("volume_profile_poc", fts)
    assert blended is not None
    assert blended.scanner_id == "volume_profile_poc"
    assert blended.n_symbols == len(fts)
    assert blended.promotion in {"promote", "keep_testing", "retire"}
    assert 0.3 <= blended.edge_weight <= 2.5
    assert 0.0 <= blended.promote_fraction <= 1.0
    # pooled OOS trades equal the sum of each symbol's OOS trades
    assert blended.total_oos_trades == sum(len(ft.out_of_sample.trades) for _, ft in fts)


def test_blend_forward_tests_empty_is_none():
    from engine.backtesting import blend_forward_tests

    assert blend_forward_tests("volume_profile_poc", []) is None
    assert blend_forward_tests("volume_profile_poc", [("A", None)]) is None  # type: ignore[list-item]


def test_blend_neutral_on_too_few_trades():
    """A scanner with very few pooled OOS trades must not earn a promote/retire verdict —
    it stays neutral (keep_testing, weight 1.0) however good/bad those few trades look."""
    from datetime import date

    from engine.backtesting import BlendedEdge, ForwardTest, blend_forward_tests
    from engine.backtesting.roster import MIN_OOS_TRADES
    from engine.schemas import BacktestResult

    def ft_with(pnls):  # build a ForwardTest whose OOS trades have these PnLs
        now = datetime(2026, 1, 2, tzinfo=UTC)
        trades = [
            TradeRecord(
                symbol="X",
                side=Side.LONG,
                entry_ts=now,
                entry_price=Decimal("100"),
                exit_ts=now,
                exit_price=Decimal("101"),
                pnl=Decimal(str(p)),
                return_pct=p / 100.0,
            )
            for p in pnls
        ]
        oos = BacktestResult(
            scanner_id="x",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 2, 1),
            trades=trades,
        )
        return ForwardTest(
            scanner_id="x",
            baseline={},
            forward={"total_trades": len(trades), "profit_factor": 9.0},
            drift={},
            monte_carlo=None,
            promotion="promote",
            rationale="",
            out_of_sample=oos,
        )

    # 5 all-winning trades (PF huge) but below the floor -> neutral, not promote
    blended = blend_forward_tests("x", [("A", ft_with([100, 100, 100, 100, 100]))])
    assert isinstance(blended, BlendedEdge)
    assert blended.total_oos_trades < MIN_OOS_TRADES
    assert blended.promotion == "keep_testing"
    assert blended.edge_weight == 1.0
