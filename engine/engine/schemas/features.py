"""Feature snapshot contract.

A FeatureSnapshot is the assembled, point-in-time evidence vector the scanners read.
Scalar features live in a namespaced ``features`` dict (e.g. ``atr.14``, ``vp.poc``,
``gex.flip``); larger artifacts (swing lists, per-strike GEX arrays) live in ``meta``.
Every feature must be "as-of safe" — computable from data known at ``ts``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import Regime, Timeframe


class FeatureSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: Timeframe
    ts: datetime
    features: dict[str, float | None] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    regime: Regime = Regime.UNKNOWN
    source_version: str = "0.1.0"

    def get(self, key: str, default: float | None = None) -> float | None:
        return self.features.get(key, default)

    def require(self, key: str) -> float:
        val = self.features.get(key)
        if val is None:
            raise KeyError(f"required feature missing: {key}")
        return val

    def with_features(self, **kv: float | None) -> FeatureSnapshot:
        merged = {**self.features, **kv}
        return self.model_copy(update={"features": merged})
