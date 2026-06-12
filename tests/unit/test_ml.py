"""ML engine: dataset, model training, anomaly, regime."""

from __future__ import annotations

from engine.ml import (
    build_dataset,
    classify_regime,
    compute_feature_frame,
    detect_last_bar,
    train_setup_model,
)
from engine.ml.dataset import FEATURE_NAMES
from tests.conftest import make_ohlcv


def test_feature_frame_columns():
    from engine.features.base import ohlcv_to_frame

    df = ohlcv_to_frame(make_ohlcv(n=120))
    feats = compute_feature_frame(df)
    assert list(feats.columns) == FEATURE_NAMES
    assert len(feats) == len(df)


def test_build_dataset_shapes():
    ds = build_dataset(make_ohlcv(n=400), horizon=10)
    assert ds is not None
    assert ds.X.shape[0] == ds.y.shape[0] == len(ds.index)
    assert ds.X.shape[1] == len(FEATURE_NAMES)
    assert set(ds.y.tolist()) <= {0, 1}


def test_train_setup_model_reports():
    report = train_setup_model(
        make_ohlcv(n=500, drift=0.05, amp=2.0), scanner_id="test", horizon=10
    )
    assert report is not None
    assert 0.0 <= report.test_accuracy <= 1.0
    assert 0.0 <= report.auc <= 1.0
    assert len(report.feature_importance) == len(FEATURE_NAMES)
    assert abs(sum(report.feature_importance.values()) - 1.0) < 0.05


def test_anomaly_detection_runs():
    res = detect_last_bar(make_ohlcv(n=300))
    assert res is not None
    assert 0.0 <= res.score <= 1.0
    assert isinstance(res.is_anomaly, bool)


def test_regime_classification_runs():
    res = classify_regime(make_ohlcv(n=400), n_regimes=4, horizon=10)
    assert res is not None
    assert 0 <= res.current_regime < res.n_regimes
    assert 0.0 <= res.regime_win_rate <= 1.0


def test_insufficient_data_returns_none():
    assert build_dataset(make_ohlcv(n=20)) is None
    assert train_setup_model(make_ohlcv(n=30)) is None
