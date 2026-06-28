"""Live regime-conditional ensemble scan — the production form of the validated 2x strategy.

For each symbol it runs a set of scanners on one point-in-time snapshot, weights each by its
*current-regime* out-of-sample edge (persisted ``regime_edges``), drops the ones with no
proven edge in this regime, and fuses the survivors with the edge-weighted consensus
(``evidence.combine``). When the consensus says trade, it emits one ensemble SignalPacket
built from the lead contributor; every contributing scanner's result is still persisted for
audit. This is the same logic proven out-of-sample in ``backtest_ensemble``.
"""

from __future__ import annotations

from uuid import UUID

import redis.asyncio as aioredis

from engine.evidence import combine
from engine.features import FeatureFactory
from engine.scanners import build_scanner
from engine.scanners.base import ScanContext
from engine.scanners.regime_affinity import regime_kind_from_er
from engine.schemas import Side, Timeframe
from engine.signals import build_signal

from ..pubsub import publish_signal
from ..repositories import repo
from .scan_service import _asset_class, _resolve_ohlcv_source, _start_for

_EDGE_FLOOR = 0.5


async def execute_ensemble_scan(session, run_id: UUID, redis: aioredis.Redis | None = None) -> int:
    """Run an ensemble scan run (scanner_id='ensemble', params['scanners']=[...])."""
    run = await repo.get_run(session, run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")
    scanner_ids = list(run.params.get("scanners") or [])
    if not scanner_ids:
        raise ValueError("ensemble scan requires params['scanners']")

    await repo.set_run_status(session, run_id, "running")
    triggered = 0
    try:
        timeframe = Timeframe(run.timeframe)
        start = _start_for(str(run.params.get("history", "1y")))
        ohlcv_src = await _resolve_ohlcv_source(session, run.params.get("data_vendor"))
        factory = FeatureFactory()

        # Per-scanner validated edge records (global + per-regime weights), fetched once.
        edge_records: dict[str, dict] = {}
        for sid in scanner_ids:
            rec = await repo.get_latest_edge_record(session, sid)
            if rec is not None:
                edge_records[sid] = rec

        for symbol in run.universe:
            ohlcv = ohlcv_src.get_ohlcv(symbol, timeframe, start)
            if len(ohlcv.bars) == 0:
                continue
            snapshot = factory.build_snapshot(ohlcv)
            regime_kind = regime_kind_from_er(snapshot.get("regime.er"))

            results = []
            weights: dict[str, float] = {}
            for sid in scanner_ids:
                w = _effective_weight(edge_records.get(sid), regime_kind)
                if w < _EDGE_FLOOR:  # no proven edge in this regime -> doesn't vote
                    continue
                ctx = ScanContext(
                    symbol=symbol,
                    timeframe=timeframe,
                    snapshot=snapshot,
                    ohlcv=ohlcv,
                    run_id=run_id,
                )
                try:
                    res = build_scanner(sid, run.params).run(ctx)
                except Exception:
                    continue
                results.append(res)
                weights[sid] = w
                await repo.save_result(session, res)  # audit trail per contributor

            cons = combine(results, edge_weights=weights)
            signal = _ensemble_signal(cons, results, snapshot, weights, symbol)
            if signal is None:
                continue
            await repo.save_signal(session, signal)
            if signal.side in (Side.LONG, Side.SHORT) and signal.entry is not None:
                triggered += 1
                if redis is not None:
                    await publish_signal(redis, str(run_id), signal.model_dump_json())

        await session.commit()
        await repo.set_run_status(session, run_id, "done")
    except Exception as exc:
        await repo.set_run_status(session, run_id, "error", error=str(exc))
        raise
    return triggered


def _effective_weight(rec: dict | None, regime_kind: str | None) -> float:
    if rec is None:
        return 1.0  # unproven -> neutral (still allowed)
    regime_edges = rec.get("regime_edges") or {}
    if regime_kind in regime_edges:
        return float(regime_edges[regime_kind])
    return float(rec.get("edge_weight", 1.0))


def _ensemble_signal(cons, results, snapshot, weights, symbol):
    """Synthesize one ensemble SignalPacket from the consensus + its lead contributor."""
    if cons.action != "trade" or cons.direction not in (Side.LONG, Side.SHORT):
        return None
    # Lead = the agreeing contributor with the highest edge-weighted score (its levels/ATR
    # anchor the trade plan).
    agreeing = [r for r in results if r.triggered and r.direction == cons.direction]
    if not agreeing:
        return None
    lead = max(agreeing, key=lambda r: r.score * weights.get(r.scanner_id, 1.0))
    sig = build_signal(
        lead, snapshot, asset_class=_asset_class(symbol), edge_weight=cons.score + 1.0
    )
    contributors = "+".join(sorted({r.scanner_id for r in agreeing}))
    return sig.model_copy(
        update={
            "source_scanner": f"ensemble:{contributors}",
            "score": round(cons.score, 4),
            "notes": (
                f"Ensemble consensus ({cons.action}) of {cons.contributors}; "
                f"{cons.agree} agree / {cons.disagree} disagree."
            ),
        }
    )
