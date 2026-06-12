"""Confidence calibration: isotonic map, Wilson band, Brier improvement, signal wiring."""

from __future__ import annotations

import random

from engine.ml import build_scanner_calibrator, fit_calibrator, wilson_interval
from engine.ml.calibration import ScoreCalibrator
from engine.signals import build_signal
from tests.conftest import make_ohlcv


def test_wilson_interval_bounds_and_width():
    lo, hi = wilson_interval(7, 10)
    assert 0 <= lo < hi <= 1
    # more samples -> tighter interval around the same proportion
    lo2, hi2 = wilson_interval(70, 100)
    assert (hi2 - lo2) < (hi - lo)


def test_fit_calibrator_is_monotonic_and_improves_brier():
    """Build mis-calibrated scores: model says p but truth is p**2 -> isotonic should fix it."""
    rng = random.Random(0)
    scores, outcomes = [], []
    for _ in range(2000):
        s = rng.random()
        true_p = s**2  # overconfident model
        scores.append(s)
        outcomes.append(1 if rng.random() < true_p else 0)
    cal = fit_calibrator(scores, outcomes)
    assert cal.fitted
    # monotonic non-decreasing calibration map
    assert all(b >= a - 1e-9 for a, b in zip(cal.y, cal.y[1:], strict=False))
    # calibration reduces Brier vs the raw (overconfident) score
    assert cal.brier_calibrated <= cal.brier_raw
    # a raw score of 0.8 should be pulled toward ~0.64 (=0.8**2)
    assert cal.apply(0.8) < 0.8
    assert abs(cal.apply(0.8) - 0.64) < 0.12


def test_calibrator_round_trips_through_dict():
    cal = fit_calibrator([i / 100 for i in range(100)] * 2, [1 if i % 2 else 0 for i in range(200)])
    again = ScoreCalibrator.from_dict(cal.to_dict())
    assert again.fitted == cal.fitted
    assert abs(again.apply(0.5) - cal.apply(0.5)) < 1e-9


def test_unfit_calibrator_is_identity():
    cal = ScoreCalibrator()
    assert cal.apply(0.73) == 0.73


def test_build_scanner_calibrator_runs():
    cal = build_scanner_calibrator(
        "mtf_structure", make_ohlcv(n=400, drift=0.05, amp=1.5), horizon=10
    )
    assert isinstance(cal, ScoreCalibrator)  # may or may not be fitted on synthetic data


def test_signal_uses_calibrated_probability():
    from datetime import UTC, datetime

    from engine.features import FeatureFactory
    from engine.scanners import ScanContext, build_scanner

    ohlcv = make_ohlcv(n=200, drift=0.1, amp=1.5)
    htf = make_ohlcv(n=120, drift=0.3)
    snap = FeatureFactory().build_snapshot(ohlcv)
    ctx = ScanContext(
        symbol="SPY",
        timeframe=ohlcv.timeframe,
        snapshot=snap,
        ohlcv=ohlcv,
        htf_ohlcv=htf,
        as_of=datetime(2026, 6, 11, tzinfo=UTC),
    )
    res = build_scanner("mtf_structure").run(ctx)
    # a fitted calibrator that maps everything to ~0.9
    cal = ScoreCalibrator(x=[0.0, 1.0], y=[0.9, 0.9], n_samples=500, fitted=True).to_dict()
    sig = build_signal(res, snap, calibrator=cal)
    if res.triggered:
        assert sig.calibrated_probability is not None
        assert abs(sig.calibrated_probability - 0.9) < 1e-6
    # without a calibrator the field stays None
    sig2 = build_signal(res, snap)
    assert sig2.calibrated_probability is None
