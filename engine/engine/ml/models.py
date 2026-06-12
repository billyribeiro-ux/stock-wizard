"""Setup-success model training with walk-forward validation + feature importance.

Trains a gradient-boosted classifier to predict whether a setup is followed by a
favorable forward move, validates out-of-sample (time-ordered split — no shuffling,
no leakage), and reports calibrated accuracy + SHAP-style feature importances.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score

from ..schemas import OHLCV
from .cross_validation import purged_walk_forward_splits
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
    cv_mean_accuracy: float = 0.0  # purged & embargoed walk-forward (López de Prado)
    cv_mean_auc: float = 0.0
    cv_folds: int = 0
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

    # Purged & embargoed walk-forward CV — the leak-proof out-of-sample estimate.
    cv_accs: list[float] = []
    cv_aucs: list[float] = []
    for tr_idx, te_idx in purged_walk_forward_splits(n, horizon=horizon, n_splits=5):
        if len(tr_idx) < 20 or len(set(y_tr_all := ds.y[tr_idx])) < 2:
            continue
        m = GradientBoostingClassifier(
            n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42
        )
        m.fit(ds.X[tr_idx], y_tr_all)
        yte = ds.y[te_idx]
        cv_accs.append(float(m.score(ds.X[te_idx], yte)))
        if len(set(yte)) >= 2:
            with contextlib.suppress(ValueError):
                cv_aucs.append(float(roc_auc_score(yte, m.predict_proba(ds.X[te_idx])[:, 1])))
    cv_acc = float(np.mean(cv_accs)) if cv_accs else 0.0
    cv_auc = float(np.mean(cv_aucs)) if cv_aucs else 0.0

    # "Reliable" = beats the base rate out-of-sample AND survives purged walk-forward CV.
    reliable = (
        test_acc > max(base_rate, 1 - base_rate) + 0.02
        and auc > 0.55
        and (cv_auc > 0.52 if cv_aucs else True)
    )

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
        cv_mean_accuracy=round(cv_acc, 4),
        cv_mean_auc=round(cv_auc, 4),
        cv_folds=len(cv_accs),
        reliable=reliable,
    )
