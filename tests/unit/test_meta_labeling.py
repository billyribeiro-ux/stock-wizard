"""Meta-labeling: secondary 'should I take this signal' model + sizing edge."""

from __future__ import annotations

from engine.ml import build_meta_model
from engine.ml.meta_labeling import MetaModel
from tests.conftest import make_ohlcv


def test_meta_model_trains_and_reports():
    res = build_meta_model("mtf_structure", make_ohlcv(n=700, drift=0.05, amp=2.0), horizon=10)
    assert isinstance(res.report, MetaModel)
    if res.report.fitted:
        assert 0.0 <= res.report.primary_win_rate <= 1.0
        assert 0.0 <= res.report.meta_cv_auc <= 1.0
        assert 0.0 <= res.report.take_fraction <= 1.0
        # lift = filtered win-rate minus primary win-rate (can be + or -)
        assert abs(res.report.lift_vs_primary) <= 1.0
        assert res.estimator is not None  # live-scoring estimator kept in-process
        assert "meta-labeling" in res.report.note.lower()


def test_meta_model_insufficient_history():
    res = build_meta_model("mtf_structure", make_ohlcv(n=80), horizon=10)
    assert not res.report.fitted
    assert res.estimator is None
