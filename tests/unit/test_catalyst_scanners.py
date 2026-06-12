"""Earnings & Guidance catalyst scanner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from engine.features import FeatureFactory
from engine.scanners import ScanContext, build_scanner
from engine.schemas import EarningsEvent, Side, Timeframe
from tests.conftest import make_ohlcv

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _ctx(earnings):
    snap = FeatureFactory().build_snapshot(make_ohlcv())
    return ScanContext(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        snapshot=snap,
        ohlcv=make_ohlcv(),
        earnings=earnings,
        as_of=NOW,
    )


def test_no_earnings_data():
    res = build_scanner("earnings_guidance").run(_ctx([]))
    assert res.triggered is False
    assert res.classification == "no_earnings_data"


def test_imminent_earnings_event_risk():
    soon = NOW.date() + timedelta(days=2)
    res = build_scanner("earnings_guidance").run(
        _ctx([EarningsEvent(symbol="AAPL", date=soon, hour="amc")])
    )
    assert res.triggered
    assert res.classification == "earnings_event_risk"
    assert res.direction is None  # event risk is non-directional


def test_post_earnings_beat_drift_long():
    past = NOW.date() - timedelta(days=1)
    res = build_scanner("earnings_guidance").run(
        _ctx([EarningsEvent(symbol="AAPL", date=past, eps_estimate=1.0, eps_actual=1.3)])
    )
    assert res.triggered
    assert res.classification == "post_earnings_drift"
    assert res.direction == Side.LONG


def test_post_earnings_miss_drift_short():
    past = NOW.date() - timedelta(days=2)
    res = build_scanner("earnings_guidance").run(
        _ctx([EarningsEvent(symbol="AAPL", date=past, eps_estimate=2.0, eps_actual=1.5)])
    )
    assert res.direction == Side.SHORT
