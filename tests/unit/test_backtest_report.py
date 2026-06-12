"""Backtest PDF/HTML report rendering."""

from __future__ import annotations

from engine.backtesting import BacktestConfig, BacktestEngine
from engine.reports import render_backtest_html, render_backtest_pdf
from tests.conftest import make_ohlcv


def _result():
    return BacktestEngine(BacktestConfig(warmup=40, min_score=0.3)).run(
        "mtf_structure", make_ohlcv(n=300, drift=0.1, amp=1.5)
    )


def test_backtest_html_has_metrics():
    html = render_backtest_html(_result())
    assert "<html" in html.lower()
    assert "Profit factor" in html
    assert "Performance" in html


def test_backtest_pdf_renders():
    pdf = render_backtest_pdf(_result())
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000
