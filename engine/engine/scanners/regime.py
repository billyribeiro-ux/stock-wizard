"""Regime & catalyst scanners that work from price history alone:
volatility-regime classification and day-of-week/month seasonality.
"""

from __future__ import annotations

import numpy as np

from ..features import squeeze as sq
from ..features.base import ohlcv_to_frame
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner


class VolatilityRegimeScanner(Scanner):
    scanner_id = "volatility_regime"
    name = "Volatility Regime"
    description = (
        "Classifies realized-vol regime (quiet/normal/expansion/panic) to gate strategies."
    )
    category = "volatility"
    default_params = {"window": 20, "hist": 252}
    params_schema = {
        "type": "object",
        "properties": {
            "window": {"type": "integer", "default": 20},
            "hist": {"type": "integer", "default": 252},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = ohlcv_to_frame(ctx.ohlcv) if ctx.ohlcv is not None else None
        if df is None or len(df) < self.params["window"] + 5:
            return flat(self, ctx, "insufficient_data", "Not enough bars.", "price")
        rv = sq.realized_vol(df, self.params["window"])
        if rv is None:
            return flat(self, ctx, "insufficient_data", "Realized vol unavailable.", "price")
        rets = np.log(df["close"] / df["close"].shift(1)).dropna()
        roll = rets.rolling(self.params["window"]).std().dropna()
        pct = 0.5 if len(roll) < 10 else float((roll.iloc[-1] >= roll).mean())
        if pct >= 0.9:
            regime = "panic"
        elif pct >= 0.66:
            regime = "expansion"
        elif pct <= 0.2:
            regime = "quiet"
        else:
            regime = "normal"
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=None,
            score=pct,
            classification=f"vol_{regime}",
            why=f"Realized volatility is in the {regime} regime ({pct:.0%} percentile).",
            why_now=f"20-bar realized vol ≈ {rv:.1%} (annualized).",
            invalidation=InvalidationRule(
                description="Volatility shifts to another regime", kind="price"
            ),
            evidence_for=[
                ev(EK.PATTERN, "rv_percentile", round(pct, 2), 0.6, Side.NEUTRAL, self.scanner_id)
            ],
            feature_refs={"realized_vol": rv, "rv_percentile": pct},
        )


class SeasonalityScanner(Scanner):
    scanner_id = "seasonality"
    name = "Seasonality & Similar-Day"
    description = "Day-of-week / month historical edge from the symbol's own return distribution."
    category = "catalyst"
    default_params = {"min_samples": 8}
    params_schema = {
        "type": "object",
        "properties": {"min_samples": {"type": "integer", "default": 8}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = ohlcv_to_frame(ctx.ohlcv) if ctx.ohlcv is not None else None
        if df is None or len(df) < 30:
            return flat(self, ctx, "insufficient_data", "Not enough bars.", "price")
        rets = df["close"].pct_change().dropna()
        dow = df.index[1:].dayofweek
        cur_dow = int(df.index[-1].dayofweek)
        same = rets[dow == cur_dow]
        if len(same) < self.params["min_samples"]:
            return flat(self, ctx, "insufficient_samples", "Not enough same-day history.", "price")
        mean = float(same.mean())
        win_rate = float((same > 0).mean())
        direction = Side.LONG if mean > 0 else Side.SHORT
        edge = abs(mean) / (float(same.std()) + 1e-9)
        triggered = edge >= 0.15 and abs(win_rate - 0.5) >= 0.08
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return make_result(
            self,
            ctx,
            triggered=triggered,
            direction=direction if triggered else None,
            score=min(1.0, edge),
            classification="seasonal_edge" if triggered else "no_edge",
            why=f"On {names[cur_dow]}, this symbol averaged {mean:+.2%} (win rate {win_rate:.0%}).",
            why_now=f"{len(same)} historical {names[cur_dow]} samples.",
            invalidation=InvalidationRule(
                description="Seasonal pattern degrades out-of-sample", kind="time"
            ),
            evidence_for=[
                ev(EK.TIME, "dow_mean_return", round(mean, 4), 0.5, direction, self.scanner_id),
                ev(EK.TIME, "dow_win_rate", round(win_rate, 2), 0.3, direction, self.scanner_id),
            ],
        )
