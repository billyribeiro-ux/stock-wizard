"""Convert a ScannerResult into a universal SignalPacket with a real trade plan.

No-trade / untriggered results still produce a packet (state stays PROPOSED with a
no-trade classification) so the audit trail is complete — the blueprint treats
'no trade' as a first-class signal.
"""

from __future__ import annotations

from ..risk import build_plan
from ..schemas import (
    AssetClass,
    FeatureSnapshot,
    Regime,
    ScannerResult,
    Side,
    SignalPacket,
    SignalState,
    TradeStyle,
)

_NO_TRADE = {"no_trade", "no_flow", "balance", "poc_balance", "inside_value", "insufficient_data"}


def _trade_style(timeframe) -> TradeStyle:
    tf = timeframe.value
    if tf in {"1m", "5m"}:
        return TradeStyle.SCALP
    if tf in {"15m", "30m", "1h"}:
        return TradeStyle.INTRADAY
    if tf in {"4h", "1d"}:
        return TradeStyle.SWING
    return TradeStyle.POSITION


def build_signal(
    result: ScannerResult,
    snapshot: FeatureSnapshot | None = None,
    asset_class: AssetClass = AssetClass.EQUITY,
    account_risk: float | None = None,
    calibrator: dict | None = None,
    edge_weight: float = 1.0,
) -> SignalPacket:
    is_no_trade = (not result.triggered) or result.classification in _NO_TRADE
    side = result.direction or Side.NEUTRAL

    # Regime gate: demote a triggered signal whose source scanner has no validated edge in
    # the current regime (e.g. a trend-only structure scanner firing in a range). The signal
    # is still recorded for audit, but no trade plan is emitted and it's flagged.
    from ..scanners.regime_affinity import is_regime_aligned

    er = (result.feature_refs or {}).get("regime.er")
    if er is None and snapshot is not None:
        er = snapshot.get("regime.er")
    regime_aligned = is_regime_aligned(result.scanner_id, er)
    gated = result.triggered and not is_no_trade and not regime_aligned

    entry_level = result.levels.get("close") or result.levels.get("spot")
    atr = (result.feature_refs or {}).get("atr.14") or (
        snapshot.get("atr.14") if snapshot else None
    )

    plan = None
    if (
        not is_no_trade
        and not gated
        and entry_level is not None
        and atr
        and atr > 0
        and side != Side.NEUTRAL
    ):
        stop_atr = 1.0
        targets = (1.5, 3.0)
        if result.timeframe.value in {"1m", "5m"}:  # tighter for scalps
            stop_atr, targets = 0.75, (1.0, 2.0)
        plan = build_plan(
            side,
            float(entry_level),
            float(atr),
            stop_atr=stop_atr,
            target_atrs=targets,
            account_risk=account_risk,
        )

    computed = ["gamma", "iv"] if result.scanner_id == "spx_gamma_command" else []

    # Calibration: remap the raw score to the historical win-rate (isotonic), if a
    # calibrator was fit for this scanner; otherwise leave it None.
    calibrated_prob: float | None = None
    band: tuple[float, float]
    if calibrator:
        from ..ml.calibration import ScoreCalibrator

        cal = ScoreCalibrator.from_dict(calibrator)
        if cal.fitted:
            calibrated_prob = round(cal.apply(result.score), 4)
            band = tuple(round(b, 4) for b in cal.band(result.score))  # type: ignore[assignment]
    if calibrated_prob is None:
        # Fall back to the Bayesian posterior band from the evidence stack.
        from ..evidence.bayesian import confidence_band

        band = confidence_band(result.evidence, prior=max(0.05, min(0.95, result.score)))

    return SignalPacket(
        run_id=result.run_id,
        source_scanner=result.scanner_id,
        symbol=result.symbol,
        asset_class=asset_class,
        timeframe=result.timeframe,
        as_of=result.ts,
        side=side,
        state=SignalState.PROPOSED,
        trade_style=_trade_style(result.timeframe),
        score=result.score,
        calibrated_probability=calibrated_prob,
        confidence_band=band,
        regime=snapshot.regime if snapshot else Regime.UNKNOWN,
        regime_aligned=regime_aligned,
        edge_weight=round(max(0.0, float(edge_weight)), 4),
        classification=result.classification,
        entry=plan.entry if plan else None,
        stop=plan.stop if plan else None,
        targets=plan.targets if plan else [],
        rr=plan.rr if plan else None,
        suggested_size=plan.size if plan else None,
        key_levels=result.levels,
        features=snapshot,
        evidence=result.evidence,
        data_sources=[result.scanner_id],
        computed_fields=computed,
        notes=_notes(is_no_trade, gated, result.scanner_id),
    )


def _notes(is_no_trade: bool, gated: bool, scanner_id: str) -> str | None:
    if gated:
        return (
            f"Regime-gated: '{scanner_id}' has no validated edge in the current regime — "
            "trade plan suppressed (logged for audit)."
        )
    if is_no_trade:
        return "No-trade / standing aside (logged for audit)."
    return None
