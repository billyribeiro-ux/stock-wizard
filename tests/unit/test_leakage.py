"""Lookahead / data-leakage auditor — proves the feature pipeline is as-of-safe."""

from __future__ import annotations

import pandas as pd

from engine.backtesting import audit_feature_lookahead
from engine.ml.dataset import compute_feature_frame
from tests.conftest import make_ohlcv


def test_ml_feature_frame_has_no_lookahead():
    """The production ML feature builder must be byte-stable under truncation."""
    report = audit_feature_lookahead(make_ohlcv(n=400, amp=2.0))
    assert report is not None
    assert report.clean, f"{report.summary}: {report.leaks[:3]}"
    assert report.n_probes >= 5
    # every feature's max change across probes is effectively zero
    assert max(report.max_abs_diff.values()) < 1e-9


def test_auditor_catches_a_leaky_feature():
    """A deliberately future-peeking feature must be flagged."""

    def leaky(df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)
        # centered rolling mean peeks at future bars -> leak
        out["centered"] = df["close"].rolling(5, center=True).mean()
        return out

    report = audit_feature_lookahead(make_ohlcv(n=300), feature_fn=leaky)
    assert report is not None
    assert not report.clean
    assert any(leak.feature == "centered" for leak in report.leaks)


def test_auditor_clean_on_pure_lagging_feature():
    def lagging(df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)
        out["sma10"] = df["close"].rolling(10).mean()  # backward-looking
        return out

    report = audit_feature_lookahead(make_ohlcv(n=300), feature_fn=lagging)
    assert report is not None and report.clean


def test_compute_feature_frame_used_by_default():
    report = audit_feature_lookahead(make_ohlcv(n=300))
    assert report is not None
    assert set(report.features_checked) == set(
        compute_feature_frame(
            __import__("engine.features.base", fromlist=["ohlcv_to_frame"]).ohlcv_to_frame(
                make_ohlcv(n=60)
            )
        ).columns
    )
