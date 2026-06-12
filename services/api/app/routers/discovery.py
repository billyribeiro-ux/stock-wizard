"""Self-Learning Discovery endpoints — replay history, self-identify buy/sell reasons.

Lookback is fully customizable (5d → 30y where data supports it) and the timeframe maps
to a trade style: 1m/5m = scalping, 15m-1h = intraday/day trading, 1d+ = swing. Results
export to CSV (event log) and PDF (reason report) via /exports/discovery/{id}.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SessionLocal, get_session
from ..jobs import enqueue_discovery
from ..repositories import repo
from ..security import require_token
from ..services.discovery_service import DISCOVERY_SCANNER_ID, execute_discovery

router = APIRouter(tags=["discovery"], dependencies=[Depends(require_token)])


class DiscoveryRequest(BaseModel):
    symbol: str
    timeframe: str = "1d"
    history: str = Field(
        default="1y", description="Custom lookback: 5d|1mo|3mo|6mo|1y|2y|5y|10y|20y|30y"
    )
    swing_k: int = Field(default=3, ge=1, le=10)
    min_move_atr: float = Field(default=1.5, ge=0.5, le=5.0)


async def _run_inline(discovery_id: UUID) -> None:
    async with SessionLocal() as session:
        await execute_discovery(session, discovery_id)


@router.post("/discovery", status_code=202)
async def create_discovery(
    req: DiscoveryRequest, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> dict:
    discovery_id = uuid4()
    params = {
        "history": req.history,
        "swing_k": req.swing_k,
        "min_move_atr": req.min_move_atr,
        "mode": "discovery",
    }
    await repo.create_backtest(
        session, discovery_id, DISCOVERY_SCANNER_ID, req.timeframe, [req.symbol.upper()], params
    )
    enqueued = await enqueue_discovery(str(discovery_id))
    if not enqueued:
        background.add_task(_run_inline, discovery_id)
    return {"discovery_id": str(discovery_id), "enqueued": enqueued}


@router.get("/discovery")
async def list_discoveries(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await repo.list_backtests(session)
    return {
        "items": [
            {
                "discovery_id": str(r.backtest_id),
                "symbol": (r.universe or ["?"])[0],
                "timeframe": r.timeframe,
                "status": r.status,
                "metrics": r.metrics,
                "params": r.params,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
            if r.scanner_id == DISCOVERY_SCANNER_ID
        ]
    }


@router.get("/discovery/{discovery_id}")
async def get_discovery(discovery_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    row = await repo.get_backtest(session, discovery_id)
    if row is None or row.scanner_id != DISCOVERY_SCANNER_ID:
        raise HTTPException(404, "discovery not found")
    return {
        "discovery_id": str(row.backtest_id),
        "symbol": (row.universe or ["?"])[0],
        "timeframe": row.timeframe,
        "status": row.status,
        "params": row.params,
        "metrics": row.metrics,
        "report": row.payload,
        "error": row.error,
        "created_at": row.created_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


@router.get("/exports/discovery/{discovery_id}")
async def export_discovery(
    discovery_id: UUID,
    fmt: str = Query("csv", pattern="^(csv|pdf)$"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await repo.get_backtest(session, discovery_id)
    if row is None or row.scanner_id != DISCOVERY_SCANNER_ID or not row.payload:
        raise HTTPException(404, "discovery not found or not finished")

    from engine.ml.discovery import (
        DiscoveryReport,
        Reason,
        ReasonStat,
        SuggestedRule,
        TurnEvent,
    )

    p = row.payload
    report = DiscoveryReport(
        symbol=p["symbol"],
        timeframe=p["timeframe"],
        trade_style=p["trade_style"],
        period_start=p["period_start"],
        period_end=p["period_end"],
        n_bars=p["n_bars"],
        n_events=p["n_events"],
        n_bought=p["n_bought"],
        n_sold=p["n_sold"],
        events=[
            TurnEvent(
                ts=e["ts"],
                kind=e["kind"],
                price=e["price"],
                forward_move_pct=e["forward_move_pct"],
                forward_move_atr=e["forward_move_atr"],
                reasons=[Reason(**r) for r in e["reasons"]],
            )
            for e in p["events"]
        ],
        buy_reasons=[ReasonStat(**s) for s in p["buy_reasons"]],
        sell_reasons=[ReasonStat(**s) for s in p["sell_reasons"]],
        baseline_buy_move=p.get("baseline_buy_move", 0.0),
        baseline_sell_move=p.get("baseline_sell_move", 0.0),
        suggested_rules=[SuggestedRule(**sr) for sr in p.get("suggested_rules", [])],
        validated_split=p.get("validated_split", 0.6),
    )

    if fmt == "csv":
        from engine.reports import discovery_to_csv

        return Response(
            content=discovery_to_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="discovery_{discovery_id}.csv"'},
        )
    try:
        from engine.reports import render_discovery_pdf

        pdf = render_discovery_pdf(report)
    except Exception as exc:
        raise HTTPException(500, f"PDF rendering unavailable: {exc}") from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="discovery_{discovery_id}.pdf"'},
    )
