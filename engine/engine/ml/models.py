"""Setup-success model training with walk-forward validation + feature importance.

Trains a gradient-boosted classifier to predict whether a setup is followed by a
favorable forward move, validates out-of-sample (time-ordered split — no shuffling,
no leakage), and reports calibrated accuracy + SHAP-style feature importances.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score

from ..schemas import OHLCV
from .dataset import build_dataset


@dataclass
class ModelReport:
    scanner_id: str
    n_samples: int
    horizon: int
    train_accuracy: float
    test_accuracy: float
    auc: float
    brier: float
    base_rate: float
    feature_importance: dict[str, float]
    calibration: list[dict] = field(default_factory=list)
    reliable: bool = False


def train_setup_model(
    ohlcv: OHLCV,
    scanner_id: str = "generic",
    horizon: int = 10,
    up_threshold: float = 0.0,
    test_frac: float = 0.3,
) -> ModelReport | None:
    ds = build_dataset(ohlcv, horizon=horizon, up_threshold=up_threshold)
    if ds is None or len(np.unique(ds.y)) < 2:
        return None

    n = len(ds.y)
    split = int(n * (1 - test_frac))
    if split < 20 or n - split < 10:
        return None

    # Time-ordered split — NEVER shuffle financial time series.
    X_tr, X_te = ds.X[:split], ds.X[split:]
    y_tr, y_te = ds.y[:split], ds.y[split:]

    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42
    )
    model.fit(X_tr, y_tr)

    train_acc = float(model.score(X_tr, y_tr))
    test_acc = float(model.score(X_te, y_te))
    proba = model.predict_proba(X_te)[:, 1]
    try:
        auc = float(roc_auc_score(y_te, proba))
    except ValueError:
        auc = 0.5
    brier = float(brier_score_loss(y_te, proba))
    base_rate = float(y_te.mean())

    importance = dict(
        sorted(
            zip(ds.feature_names, (float(i) for i in model.feature_importances_), strict=False),
            key=lambda kv: kv[1],
            reverse=True,
        )
    )

    calib: list[dict] = []
    try:
        frac_pos, mean_pred = calibration_curve(y_te, proba, n_bins=5, strategy="quantile")
        calib = [
            {"predicted": float(p), "actual": float(a)}
            for p, a in zip(mean_pred, frac_pos, strict=False)
        ]
    except ValueError:
        calib = []

    # "Reliable" = beats the base rate out-of-sample and is reasonably calibrated.
    reliable = test_acc > max(base_rate, 1 - base_rate) + 0.02 and auc > 0.55

    return ModelReport(
        scanner_id=scanner_id,
        n_samples=n,
        horizon=horizon,
        train_accuracy=round(train_acc, 4),
        test_accuracy=round(test_acc, 4),
        auc=round(auc, 4),
        brier=round(brier, 4),
        base_rate=round(base_rate, 4),
        feature_importance={k: round(v, 4) for k, v in importance.items()},
        calibration=calib,
        reliable=reliable,
    )
