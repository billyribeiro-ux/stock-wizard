"""ML / self-learning scanners (§6.5): anomaly detection and regime classification."""

from __future__ import annotations

from ..ml import classify_regime, detect_last_bar
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner


class AnomalyDetectionScanner(Scanner):
    scanner_id = "anomaly_detection"
    name = "Anomaly Detection"
    description = (
        "IsolationForest flags bars whose feature signature is abnormal vs recent history."
    )
    category = "ml"
    default_params = {"lookback": 250, "contamination": 0.05}
    params_schema = {
        "type": "object",
        "properties": {
            "lookback": {"type": "integer", "default": 250},
            "contamination": {"type": "number", "default": 0.05},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        if ctx.ohlcv is None:
            return flat(self, ctx, "insufficient_data", "No price history.")
        res = detect_last_bar(
            ctx.ohlcv, int(self.params["lookback"]), float(self.params["contamination"])
        )
        if res is None:
            return flat(self, ctx, "insufficient_data", "Not enough history for anomaly model.")
        if res.is_anomaly:
            top = ", ".join(f"{k}={v:+.1f}σ" for k, v in res.feature_z.items())
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=None,
                score=res.score,
                classification="anomaly",
                why="The latest bar's feature signature is abnormal vs recent history.",
                why_now=f"Isolation score {res.score:.2f}; drivers: {top}.",
                invalidation=InvalidationRule(
                    description="Behavior reverts to normal", kind="price"
                ),
                evidence_for=[
                    ev(EK.PATTERN, "anomaly_score", res.score, 0.6, Side.NEUTRAL, self.scanner_id)
                ],
                feature_refs={"anomaly_score": res.score},
            )
        return flat(self, ctx, "normal", "No anomaly on the latest bar.")


class RegimeClassificationScanner(Scanner):
    scanner_id = "regime_classification"
    name = "Regime Classification Engine"
    description = (
        "KMeans clusters bars into regimes; reports the current regime's forward-return edge."
    )
    category = "ml"
    default_params = {"n_regimes": 4, "horizon": 10, "min_samples": 20}
    params_schema = {
        "type": "object",
        "properties": {
            "n_regimes": {"type": "integer", "default": 4},
            "horizon": {"type": "integer", "default": 10},
            "min_samples": {"type": "integer", "default": 20},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        if ctx.ohlcv is None:
            return flat(self, ctx, "insufficient_data", "No price history.")
        res = classify_regime(ctx.ohlcv, int(self.params["n_regimes"]), int(self.params["horizon"]))
        if res is None:
            return flat(self, ctx, "insufficient_data", "Not enough history for regime model.")
        enough = res.sample_size >= self.params["min_samples"]
        edge = abs(res.regime_forward_bias)
        triggered = enough and edge >= 0.002 and abs(res.regime_win_rate - 0.5) >= 0.06
        direction = Side.LONG if res.regime_forward_bias > 0 else Side.SHORT
        return make_result(
            self,
            ctx,
            triggered=triggered,
            direction=direction if triggered else None,
            score=min(1.0, edge * 50),
            classification=f"regime_{res.current_regime}",
            why=(
                f"Current regime #{res.current_regime} of {res.n_regimes} historically led to "
                f"{res.regime_forward_bias:+.2%} over {self.params['horizon']} bars "
                f"(win rate {res.regime_win_rate:.0%})."
            ),
            why_now=f"{res.sample_size} historical bars share this regime signature.",
            invalidation=InvalidationRule(
                description="Regime shifts (cluster reassignment)", kind="price"
            ),
            evidence_for=[
                ev(
                    EK.PATTERN,
                    "regime_forward_bias",
                    res.regime_forward_bias,
                    0.5,
                    direction,
                    self.scanner_id,
                ),
                ev(
                    EK.PATTERN,
                    "regime_win_rate",
                    res.regime_win_rate,
                    0.3,
                    direction,
                    self.scanner_id,
                ),
            ],
        )
