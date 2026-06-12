"""Confidence calibration — make a scanner's score mean what it says.

A raw scanner score of 0.7 is meaningless unless setups scored ~0.7 actually win ~70%
of the time. This module fits a monotonic **isotonic** map from raw score to the
empirical win-rate over history, and reports a distribution-free **Wilson** interval so
the confidence band reflects real sample size. Calibrators serialize to plain dicts
(JSONB-friendly) so they persist in the model registry and apply to live signals.

This is the "honest probability" layer: a 90%% signal must behave like 90%% in
forward results, or it gets pulled back toward the base rate automatically.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from sklearn.isotonic import IsotonicRegression


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (distribution-free, small-n safe)."""
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


@dataclass
class ScoreCalibrator:
    """Isotonic score→probability map with Wilson bands, serializable to a dict."""

    x: list[float] = field(default_factory=list)  # sorted score knots
    y: list[float] = field(default_factory=list)  # calibrated probabilities
    n_samples: int = 0
    base_rate: float = 0.5
    brier_raw: float = 0.0
    brier_calibrated: float = 0.0
    fitted: bool = False

    def apply(self, score: float) -> float:
        if not self.fitted or not self.x:
            return float(score)
        return float(np.interp(score, self.x, self.y, left=self.y[0], right=self.y[-1]))

    def band(self, score: float, halfwidth: float = 0.1) -> tuple[float, float]:
        """Wilson interval from the calibration samples near this score."""
        if not self.fitted or self.n_samples == 0:
            return (max(0.0, score - 0.25), min(1.0, score + 0.25))
        p = self.apply(score)
        # effective local sample size (samples are spread across knots)
        local_n = max(5, int(self.n_samples * (2 * halfwidth)))
        return wilson_interval(round(p * local_n), local_n)

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "n_samples": self.n_samples,
            "base_rate": self.base_rate,
            "brier_raw": self.brier_raw,
            "brier_calibrated": self.brier_calibrated,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> ScoreCalibrator:
        if not d:
            return cls()
        return cls(
            x=list(d.get("x", [])),
            y=list(d.get("y", [])),
            n_samples=int(d.get("n_samples", 0)),
            base_rate=float(d.get("base_rate", 0.5)),
            brier_raw=float(d.get("brier_raw", 0.0)),
            brier_calibrated=float(d.get("brier_calibrated", 0.0)),
            fitted=bool(d.get("fitted", False)),
        )


def fit_calibrator(scores: list[float], outcomes: list[int], n_knots: int = 20) -> ScoreCalibrator:
    """Fit isotonic calibration from (score, win/loss) pairs."""
    s = np.asarray(scores, dtype=float)
    o = np.asarray(outcomes, dtype=float)
    n = len(s)
    if n < 30 or len(np.unique(o)) < 2:
        base = float(o.mean()) if n else 0.5
        return ScoreCalibrator(n_samples=n, base_rate=base, fitted=False)

    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit(s, o)
    knots = np.linspace(float(s.min()), float(s.max()), n_knots)
    cal = iso.predict(knots)
    base = float(o.mean())
    brier_raw = float(np.mean((s - o) ** 2))
    brier_cal = float(np.mean((iso.predict(s) - o) ** 2))
    return ScoreCalibrator(
        x=[float(k) for k in knots],
        y=[float(c) for c in cal],
        n_samples=n,
        base_rate=round(base, 4),
        brier_raw=round(brier_raw, 5),
        brier_calibrated=round(brier_cal, 5),
        fitted=True,
    )
