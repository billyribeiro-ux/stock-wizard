"""Backtesting engine + metrics + walk-forward / forward testing."""

from .engine import BacktestConfig, BacktestEngine
from .failure import FailureAnalysis, analyze_failures
from .leakage import Leak, LeakageReport, audit_feature_lookahead
from .metrics import compute_metrics, max_drawdown
from .options_bt import (
    Leg,
    backtest_structure,
    bwb_builder,
    payoff_at_expiry,
    price_structure,
    vertical_builder,
)
from .portfolio import backtest_portfolio
from .roster import BlendedEdge, blend_forward_tests
from .walkforward import ForwardTest, MonteCarlo, forward_test, monte_carlo, walk_forward

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "compute_metrics",
    "max_drawdown",
    "forward_test",
    "walk_forward",
    "monte_carlo",
    "ForwardTest",
    "MonteCarlo",
    "analyze_failures",
    "FailureAnalysis",
    "audit_feature_lookahead",
    "LeakageReport",
    "Leak",
    "Leg",
    "payoff_at_expiry",
    "price_structure",
    "bwb_builder",
    "vertical_builder",
    "backtest_structure",
    "backtest_portfolio",
    "blend_forward_tests",
    "BlendedEdge",
]
