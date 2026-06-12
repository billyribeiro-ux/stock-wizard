"""Meta-labeling (López de Prado) — a secondary model that decides *whether to act* on a
primary signal and how big to size it.

The primary scanner answers "long or short?". Meta-labeling trains a separate classifier
on the *primary signal's own history* to answer "should I take THIS signal?" — learning
the conditions under which the primary is right vs wrong. Position size scales with the
meta-model's calibrated probability (a soft Kelly fraction). This decouples direction
from conviction and is the single highest-ROI ML overlay in modern quant practice.

We label each historical primary trigger 1 (the primary was right over the horizon) or 0
(wrong), build features from the FeatureFactory snapshot at the trigger, and fit a
gradient-boosted meta-model with purged walk-forward validation so the meta-edge is real.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from ..schemas import OHLCV, Side
from .cross_validation import purged_walk_forward_splits
from .dataset import FEATURE_NAMES, compute_feature_frame


@dataclass
class MetaModel:
    """Serializable meta-model: which primary triggers are worth taking."""

    feature_names: list[str] = field(default_factory=list)
    # GB models don't serialize to plain dict cleanly; we store a calibrated lookup of
    # leaf-free summary instead: the fitted estimator is kept in-process for scoring and
    # the report captures its validated quality.
    n_triggers: int = 0
    primary_win_rate: float = 0.0  # base hit-rate of the raw primary
    meta_cv_auc: float = 0.0  # purged-CV AUC of the meta-model
    meta_precision_at_threshold: float = 0.0
    take_fraction: float = 0.0  # fraction of triggers the meta-model would take
    lift_vs_primary: float = 0.0  # filtered win-rate - primary win-rate
    fitted: bool = False
    note: str = (
        "Meta-labeling decides whether to act on a primary signal; size by meta-probability. "
        "Validated with purged walk-forward CV — never trade unvalidated."
    )


@dataclass
class MetaResult:
    report: MetaModel
    estimator: object | None = None  # in-process GradientBoostingClassifier for live scoring


def build_meta_model(
    scanner_id: str,
    ohlcv: OHLCV,
    params: dict | None = None,
    horizon: int = 10,
    warmup: int = 80,
    take_threshold: float = 0.55,
) -> MetaResult:
    """Replay the primary scanner, label right/wrong, fit + validate the meta-model."""
    from ..features import FeatureFactory  # local import avoids ml<->scanners cycle
    from ..scanners import build_scanner
    from ..scanners.base import ScanContext

    bars = ohlcv.bars
    if len(bars) < warmup + horizon + 40:
        return MetaResult(MetaModel())
    closes = [float(b.close) for b in bars]
    feats_full = compute_feature_frame(
        __import__("engine.features.base", fromlist=["ohlcv_to_frame"]).ohlcv_to_frame(ohlcv)
    )
    factory = FeatureFactory()
    scanner = build_scanner(scanner_id, params)

    X: list[list[float]] = []
    y: list[int] = []
    for i in range(warmup, len(bars) - horizon):
        window = OHLCV(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            asset_class=ohlcv.asset_class,
            source=ohlcv.source,
            bars=bars[: i + 1],
        )
        snap = factory.build_snapshot(window)
        ctx = ScanContext(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            snapshot=snap,
            ohlcv=window,
            as_of=bars[i].ts,
        )
        res = scanner.run(ctx)
        if not res.triggered or res.direction not in (Side.LONG, Side.SHORT):
            continue
        row = feats_full.iloc[i]
        if row.isna().any():
            continue
        fwd = (closes[i + horizon] - closes[i]) / closes[i]
        correct = 1 if (fwd > 0) == (res.direction == Side.LONG) else 0
        X.append([float(row[f]) for f in FEATURE_NAMES])
        y.append(correct)

    if len(y) < 60 or len(set(y)) < 2:
        m = MetaModel(n_triggers=len(y), primary_win_rate=round(float(np.mean(y)), 4) if y else 0.0)
        return MetaResult(m)

    Xa, ya = np.asarray(X), np.asarray(y)
    primary_wr = float(ya.mean())

    # purged walk-forward AUC + filtered win-rate on out-of-sample folds
    aucs, taken, taken_wins = [], 0, 0
    for tr, te in purged_walk_forward_splits(len(ya), horizon=horizon, n_splits=5):
        if len(tr) < 30 or len(set(ya[tr])) < 2:
            continue
        gb = GradientBoostingClassifier(
            n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42
        )
        gb.fit(Xa[tr], ya[tr])
        proba = gb.predict_proba(Xa[te])[:, 1]
        if len(set(ya[te])) >= 2:
            with contextlib.suppress(ValueError):
                aucs.append(float(roc_auc_score(ya[te], proba)))
        take_mask = proba >= take_threshold
        taken += int(take_mask.sum())
        taken_wins += int(ya[te][take_mask].sum())

    meta_auc = float(np.mean(aucs)) if aucs else 0.0
    filtered_wr = (taken_wins / taken) if taken else primary_wr
    take_frac = taken / max(len(ya), 1)

    # final estimator on all data for live scoring
    final = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42
    )
    final.fit(Xa, ya)

    report = MetaModel(
        feature_names=list(FEATURE_NAMES),
        n_triggers=len(ya),
        primary_win_rate=round(primary_wr, 4),
        meta_cv_auc=round(meta_auc, 4),
        meta_precision_at_threshold=round(filtered_wr, 4),
        take_fraction=round(take_frac, 4),
        lift_vs_primary=round(filtered_wr - primary_wr, 4),
        fitted=True,
    )
    return MetaResult(report=report, estimator=final)
