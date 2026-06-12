"""Backtest endpoints — create (enqueue/inline), status/result, list."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from engine.scanners import list_scanner_ids

from ..db import SessionLocal, get_session
from ..jobs import enqueue_backtest
from ..repositories import repo
from ..security import require_token
from ..services.backtest_service import execute_backtest

router = APIRouter(tags=["backtests"], dependencies=[Depends(require_token)])

# Option/flow scanners need historical chains/filings not available for replay in v1.
BACKTESTABLE = {"mtf_structure", "volume_profile_poc"}


class BacktestRequest(BaseModel):
    scanner_id: str
    symbol: str
    timeframe: str = "1d"
    history: str = "5y"
    params: dict = Field(default_factory=dict)


async def _run_inline(backtest_id: UUID) -> None:
    async with SessionLocal() as session:
        await execute_backtest(session, backtest_id)


@router.post("/backtests", status_code=202)
async def create_backtest(
    req: BacktestRequest, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> dict:
    if req.scanner_id not in list_scanner_ids():
        raise HTTPException(404, f"unknown scanner_id: {req.scanner_id}")
    if req.scanner_id not in BACKTESTABLE:
        raise HTTPException(
            422, f"scanner '{req.scanner_id}' is not yet backtestable (needs historical chains)"
        )
    bt_id = uuid4()
    params = {**req.params, "history": req.history}
    await repo.create_backtest(
        session, bt_id, req.scanner_id, req.timeframe, [req.symbol.upper()], params
    )
    enqueued = await enqueue_backtest(str(bt_id))
    if not enqueued:
        background.add_task(_run_inline, bt_id)
    return {"backtest_id": str(bt_id), "enqueued": enqueued}


@router.get("/backtests")
async def list_backtests(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await repo.list_backtests(session)
    return {
        "items": [
            {
                "backtest_id": str(r.backtest_id),
                "scanner_id": r.scanner_id,
                "timeframe": r.timeframe,
                "universe": r.universe,
                "status": r.status,
                "metrics": r.metrics,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/backtests/{backtest_id}")
async def get_backtest(backtest_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    bt = await repo.get_backtest(session, backtest_id)
    if bt is None:
        raise HTTPException(404, "backtest not found")
    return {
        "backtest_id": str(bt.backtest_id),
        "scanner_id": bt.scanner_id,
        "status": bt.status,
        "timeframe": bt.timeframe,
        "universe": bt.universe,
        "params": bt.params,
        "metrics": bt.metrics,
        "result": bt.payload,
        "error": bt.error,
        "created_at": bt.created_at.isoformat(),
        "finished_at": bt.finished_at.isoformat() if bt.finished_at else None,
    }
