"""Information-theoretic feature selection (the blueprint's "entropy, mutual
information, information gain, feature redundancy").

Mutual information measures how much knowing a feature reduces uncertainty about the
forward outcome — it captures *non-linear* dependence a correlation would miss. We rank
features by MI with the forward direction, and flag redundancy via pairwise MI so the
self-learning loop keeps informative, non-duplicative evidence and drops noise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_selection import mutual_info_classif

from ..schemas import OHLCV
from .dataset import build_dataset


def binary_entropy(p: float) -> float:
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


@dataclass
class FeatureInfo:
    feature: str
    mutual_information: float  # bits-ish (nats from sklearn), higher = more informative
    information_gain_pct: float  # MI / label entropy


@dataclass
class InfoReport:
    label_entropy: float
    base_rate: float
    n_samples: int
    rankings: list[FeatureInfo] = field(default_factory=list)
    redundant_pairs: list[tuple[str, str, float]] = field(default_factory=list)


def mutual_information_ranking(
    ohlcv: OHLCV, horizon: int = 10, redundancy_threshold: float = 0.5
) -> InfoReport | None:
    ds = build_dataset(ohlcv, horizon=horizon)
    if ds is None or len(np.unique(ds.y)) < 2:
        return None

    base = float(ds.y.mean())
    h = binary_entropy(base)
    mi = mutual_info_classif(ds.X, ds.y, random_state=42)
    rankings = sorted(
        (
            FeatureInfo(
                feature=name,
                mutual_information=round(float(m), 5),
                information_gain_pct=round(float(m) / h, 4) if h > 0 else 0.0,
            )
            for name, m in zip(ds.feature_names, mi, strict=False)
        ),
        key=lambda f: f.mutual_information,
        reverse=True,
    )

    # Redundancy: features whose pairwise MI (discretized) is high carry the same info.
    redundant: list[tuple[str, str, float]] = []
    top = [f.feature for f in rankings[:8]]
    idx = {n: i for i, n in enumerate(ds.feature_names)}
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            xi = _discretize(ds.X[:, idx[top[i]]])
            xj = ds.X[:, idx[top[j]]]
            m = float(mutual_info_classif(xj.reshape(-1, 1), xi, random_state=0)[0])
            if m >= redundancy_threshold:
                redundant.append((top[i], top[j], round(m, 4)))

    return InfoReport(
        label_entropy=round(h, 4),
        base_rate=round(base, 4),
        n_samples=len(ds.y),
        rankings=rankings,
        redundant_pairs=redundant,
    )


def _discretize(x: np.ndarray, bins: int = 5) -> np.ndarray:
    qs = np.quantile(x, np.linspace(0, 1, bins + 1)[1:-1])
    return np.digitize(x, qs)
