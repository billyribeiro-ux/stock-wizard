"""Anomaly detection over recent feature vectors (IsolationForest)."""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.ensemble import IsolationForest

from ..features.base import ohlcv_to_frame
from ..schemas import OHLCV
from .dataset import compute_feature_frame


@dataclass
class AnomalyResult:
    is_anomaly: bool
    score: float  # higher = more anomalous (0..1)
    feature_z: dict[str, float]


def detect_last_bar(
    ohlcv: OHLCV, lookback: int = 250, contamination: float = 0.05
) -> AnomalyResult | None:
    df = ohlcv_to_frame(ohlcv)
    if len(df) < 60:
        return None
    feats = compute_feature_frame(df).dropna()
    if len(feats) < 40:
        return None
    window = feats.iloc[-lookback:]
    X = window.to_numpy(dtype=float)
    model = IsolationForest(contamination=contamination, random_state=42, n_estimators=200)
    model.fit(X)
    raw = model.score_samples(X)  # lower = more anomalous
    last_raw = raw[-1]
    # normalize: map to 0..1 where 1 = most anomalous
    score = float((raw.max() - last_raw) / (raw.max() - raw.min() + 1e-9))
    is_anom = bool(model.predict(X[-1:].reshape(1, -1))[0] == -1)
    mean, std = X.mean(axis=0), X.std(axis=0) + 1e-9
    z = (X[-1] - mean) / std
    feature_z = dict(
        sorted(
            zip(window.columns, (float(v) for v in z), strict=False),
            key=lambda kv: abs(kv[1]),
            reverse=True,
        )[:5]
    )
    return AnomalyResult(
        is_anomaly=is_anom,
        score=round(score, 4),
        feature_z={k: round(v, 2) for k, v in feature_z.items()},
    )
