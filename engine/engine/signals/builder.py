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
) -> SignalPacket:
    is_no_trade = (not result.triggered) or result.classification in _NO_TRADE
    side = result.direction or Side.NEUTRAL

    entry_level = result.levels.get("close") or result.levels.get("spot")
    atr = (result.feature_refs or {}).get("atr.14") or (
        snapshot.get("atr.14") if snapshot else None
    )

    plan = None
    if not is_no_trade and entry_level is not None and atr and atr > 0 and side != Side.NEUTRAL:
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
        regime=snapshot.regime if snapshot else Regime.UNKNOWN,
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
        notes=None if not is_no_trade else "No-trade / standing aside (logged for audit).",
    )
