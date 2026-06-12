"""User Rule Builder scanner — evaluate a user-defined (or genetically mined) rule.

The rule is supplied via params as a direction plus a conjunction of feature
conditions over the ML feature vocabulary (``ret_1``, ``rsi14``, ``rvol``,
``dist_sma20_atr``, ``bb_pctb``, ``obv_slope``, ...). This makes the dashboard's rule
builder a first-class scanner: any rule a user (or the genetic miner) writes can run
live, be backtested by the standard engine, alerted on, and exported — the full
hypothesis-lab loop.

Example params::

    {"direction": "LONG",
     "conditions": [{"feature": "rsi14", "op": "lt", "threshold": 32},
                    {"feature": "rvol", "op": "gt", "threshold": 1.4}],
     "name": "Oversold + participation"}
"""

from __future__ import annotations

import numpy as np

from ..features.base import ohlcv_to_frame
from ..ml.dataset import FEATURE_NAMES, compute_feature_frame
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner

_OPS = {"gt": ">", "lt": "<"}


class CustomRuleScanner(Scanner):
    scanner_id = "custom_rule"
    name = "User Rule Builder"
    description = (
        "Evaluates a user-defined conjunction of feature conditions as a live scanner — "
        "build a hypothesis, scan it, backtest it, alert on it."
    )
    category = "ml"
    default_params = {"direction": "LONG", "conditions": [], "name": "custom rule"}
    params_schema = {
        "type": "object",
        "properties": {
            "direction": {"type": "string", "enum": ["LONG", "SHORT"], "default": "LONG"},
            "name": {"type": "string", "default": "custom rule"},
            "conditions": {
                "type": "array",
                "title": "Conditions (ALL must hold)",
                "items": {
                    "type": "object",
                    "properties": {
                        "feature": {"type": "string", "enum": FEATURE_NAMES},
                        "op": {"type": "string", "enum": ["gt", "lt"]},
                        "threshold": {"type": "number"},
                    },
                    "required": ["feature", "op", "threshold"],
                },
            },
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        conditions = self._p("conditions", ctx) or []
        direction_s = str(self._p("direction", ctx) or "LONG").upper()
        rule_name = str(self._p("name", ctx) or "custom rule")
        if not conditions:
            return flat(self, ctx, "no_conditions", "Rule has no conditions defined.")
        if ctx.ohlcv is None or len(ctx.ohlcv) < 30:
            return flat(self, ctx, "insufficient_data", "Not enough bars to evaluate the rule.")

        feats = compute_feature_frame(ohlcv_to_frame(ctx.ohlcv))
        row = feats.iloc[-1]
        held: list[str] = []
        failed: list[str] = []
        for c in conditions:
            f, op = c.get("feature"), c.get("op")
            thr = float(c.get("threshold", 0))
            if f not in FEATURE_NAMES or op not in _OPS:
                failed.append(f"invalid:{f}")
                continue
            val = row.get(f)
            desc = f"{f} {_OPS[op]} {thr:g}"
            if val is None or (isinstance(val, float) and np.isnan(val)):
                failed.append(f"{desc} (no data)")
                continue
            ok = val > thr if op == "gt" else val < thr
            (held if ok else failed).append(f"{desc} [{val:.3f}]")

        triggered = bool(held) and not failed
        direction = Side.LONG if direction_s == "LONG" else Side.SHORT
        frac = len(held) / max(len(conditions), 1)
        return make_result(
            self,
            ctx,
            triggered=triggered,
            direction=direction if triggered else None,
            score=frac if triggered else 0.3 * frac,
            classification="rule_hit" if triggered else "rule_miss",
            why=f"User rule '{rule_name}': {len(held)}/{len(conditions)} conditions hold.",
            why_now=("All conditions satisfied: " + "; ".join(held))
            if triggered
            else ("Blocked by: " + "; ".join(failed[:3])),
            invalidation=InvalidationRule(
                description="Any rule condition stops holding", kind="price"
            ),
            evidence_for=[
                ev(EK.PATTERN, "condition", h, 0.8 / max(len(held), 1), direction, self.scanner_id)
                for h in held
            ],
            evidence_against=[
                ev(
                    EK.PATTERN,
                    "blocked_by",
                    f,
                    0.5 / max(len(failed), 1),
                    Side.NEUTRAL,
                    self.scanner_id,
                )
                for f in failed[:5]
            ],
        )
