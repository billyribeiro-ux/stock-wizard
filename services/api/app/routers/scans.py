"""Scan run endpoints — create (enqueue/inline), status, results, signals."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from engine.scanners import list_scanner_ids

from ..db import SessionLocal, get_session
from ..jobs import enqueue_scan
from ..pubsub import get_redis
from ..repositories import repo
from ..security import require_token
from ..services.scan_service import execute_scan

router = APIRouter(tags=["scans"], dependencies=[Depends(require_token)])


class ScanRequest(BaseModel):
    scanner_id: str
    symbols: list[str] = Field(min_length=1)
    timeframe: str = "5m"
    history: str = "6mo"
    params: dict = Field(default_factory=dict)


async def _run_inline(run_id: UUID) -> None:
    """Fallback execution when no worker/Redis queue is available."""
    redis = get_redis()
    async with SessionLocal() as session:
        try:
            await execute_scan(session, run_id, redis=redis)
        finally:
            await redis.aclose()


@router.post("/scans", status_code=202)
async def create_scan(
    req: ScanRequest, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> dict:
    if req.scanner_id not in list_scanner_ids():
        raise HTTPException(404, f"unknown scanner_id: {req.scanner_id}")
    run_id = uuid4()
    params = {**req.params, "history": req.history}
    await repo.create_run(
        session, run_id, req.scanner_id, req.timeframe, [s.upper() for s in req.symbols], params
    )
    enqueued = await enqueue_scan(str(run_id))
    if not enqueued:
        background.add_task(_run_inline, run_id)
    return {"run_id": str(run_id), "enqueued": enqueued}


@router.get("/scans/{run_id}")
async def get_scan(run_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    run = await repo.get_run(session, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return {
        "run_id": str(run.run_id),
        "scanner_id": run.scanner_id,
        "status": run.status,
        "timeframe": run.timeframe,
        "universe": run.universe,
        "created_at": run.created_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": run.error,
    }


@router.get("/scans/{run_id}/results")
async def get_scan_results(run_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    items = await repo.list_results(session, run_id)
    return {"items": items, "total": len(items)}
