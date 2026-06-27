"""Lookahead / data-leakage auditor.

The platform's first rule is "no lookahead": a feature computed at bar *t* must use only
information available at *t*. This auditor *proves* it empirically rather than trusting
the code: it recomputes features on the full series and on the series truncated at
several probe points, and checks that the feature row at the probe is byte-for-byte
identical. If appending future bars changes a past feature value, the pipeline leaks.

This guards the whole research stack — every ML model, the genetic miner, discovery,
and any vectorized feature — against the most insidious backtesting bug.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..features.base import ohlcv_to_frame
from ..ml.dataset import compute_feature_frame
from ..schemas import OHLCV


@dataclass
class Leak:
    feature: str
    ts: str
    full_value: float
    truncated_value: float
    abs_diff: float


@dataclass
class LeakageReport:
    features_checked: list[str]
    n_probes: int
    clean: bool
    leaks: list[Leak] = field(default_factory=list)
    max_abs_diff: dict[str, float] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        if self.clean:
            return f"No lookahead detected across {self.n_probes} probes / {len(self.features_checked)} features."
        return (
            f"LEAKAGE: {len(self.leaks)} feature/probe values changed when future bars were added."
        )


def audit_feature_lookahead(
    ohlcv: OHLCV,
    feature_fn: Callable[[pd.DataFrame], pd.DataFrame] = compute_feature_frame,
    n_probes: int = 8,
    warmup: int = 50,
    tol: float = 1e-9,
) -> LeakageReport | None:
    """Recompute features on truncated histories and confirm past values are stable."""
    df = ohlcv_to_frame(ohlcv)
    if len(df) < warmup + 10:
        return None

    full = feature_fn(df)
    features = list(full.columns)
    # Evenly spaced probe points across the post-warmup region.
    probe_space = np.linspace(warmup, len(df) - 2, num=min(n_probes, len(df) - warmup - 1))
    probes = sorted({int(p) for p in probe_space})

    leaks: list[Leak] = []
    max_diff: dict[str, float] = dict.fromkeys(features, 0.0)
    for t in probes:
        truncated = feature_fn(df.iloc[: t + 1])
        if t not in range(len(truncated)) and df.index[t] not in truncated.index:
            continue
        full_row = full.loc[df.index[t]]
        trunc_row = truncated.loc[df.index[t]]
        for feat in features:
            fv, tv = full_row[feat], trunc_row[feat]
            if pd.isna(fv) and pd.isna(tv):
                continue
            diff = float("inf") if pd.isna(fv) != pd.isna(tv) else abs(float(fv) - float(tv))
            max_diff[feat] = max(max_diff[feat], diff if diff != float("inf") else 1e9)
            if diff > tol:
                leaks.append(
                    Leak(
                        feature=feat,
                        ts=df.index[t].isoformat(),
                        full_value=float(fv) if not pd.isna(fv) else float("nan"),
                        truncated_value=float(tv) if not pd.isna(tv) else float("nan"),
                        abs_diff=diff,
                    )
                )

    return LeakageReport(
        features_checked=features,
        n_probes=len(probes),
        clean=len(leaks) == 0,
        leaks=leaks,
        max_abs_diff={k: round(v, 12) for k, v in max_diff.items()},
    )
