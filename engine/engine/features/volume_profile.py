"""Volume Profile: POC, Value Area High/Low via a volume-by-price histogram.

Each bar's volume is distributed across the price buckets its high-low range spans
(uniform split), giving a volume-at-price distribution. The Value Area is grown
outward from the POC, always adding the higher-volume adjacent bucket, until it
covers ``value_area_pct`` (default 70%) of total volume.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VolumeProfile:
    poc: float
    vah: float
    val: float
    bucket_centers: list[float]
    bucket_volume: list[float]
    total_volume: float

    @property
    def value_area_width(self) -> float:
        return self.vah - self.val


def compute_profile(
    df: pd.DataFrame, n_buckets: int = 50, value_area_pct: float = 0.70
) -> VolumeProfile | None:
    if df.empty or df["volume"].sum() <= 0:
        return None

    lo = float(df["low"].min())
    hi = float(df["high"].max())
    if hi <= lo:
        hi = lo + 1e-6

    edges = np.linspace(lo, hi, n_buckets + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    vol = np.zeros(n_buckets, dtype=float)

    # Distribute each bar's volume uniformly across the buckets its range overlaps.
    for _, row in df.iterrows():
        b_lo, b_hi, b_vol = float(row["low"]), float(row["high"]), float(row["volume"])
        if b_vol <= 0:
            continue
        if b_hi <= b_lo:
            idx = min(int(np.searchsorted(edges, b_lo, side="right") - 1), n_buckets - 1)
            vol[max(idx, 0)] += b_vol
            continue
        lo_idx = max(int(np.searchsorted(edges, b_lo, side="right") - 1), 0)
        hi_idx = min(int(np.searchsorted(edges, b_hi, side="right") - 1), n_buckets - 1)
        span = hi_idx - lo_idx + 1
        vol[lo_idx : hi_idx + 1] += b_vol / span

    total = float(vol.sum())
    poc_idx = int(np.argmax(vol))

    # Grow the value area outward from the POC.
    target = total * value_area_pct
    lo_i = hi_i = poc_idx
    covered = vol[poc_idx]
    while covered < target and (lo_i > 0 or hi_i < n_buckets - 1):
        below = vol[lo_i - 1] if lo_i > 0 else -1.0
        above = vol[hi_i + 1] if hi_i < n_buckets - 1 else -1.0
        if above >= below:
            hi_i += 1
            covered += vol[hi_i]
        else:
            lo_i -= 1
            covered += vol[lo_i]

    return VolumeProfile(
        poc=float(centers[poc_idx]),
        vah=float(centers[hi_i]),
        val=float(centers[lo_i]),
        bucket_centers=[float(c) for c in centers],
        bucket_volume=[float(v) for v in vol],
        total_volume=total,
    )
