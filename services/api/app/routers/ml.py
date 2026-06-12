"""ML / self-learning endpoints: train setup-success models, list, inspect."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SessionLocal, get_session
from ..jobs import enqueue_training
from ..repositories import repo
from ..security import require_token
from ..services.ml_service import execute_training

router = APIRouter(tags=["ml"], dependencies=[Depends(require_token)])


class TrainRequest(BaseModel):
    scanner_id: str = "generic"
    symbol: str
    timeframe: str = "1d"
    history: str = "5y"
    horizon: int = Field(default=10, ge=1, le=120)


async def _run_inline(model_id, scanner_id, symbol, timeframe, history, horizon) -> None:
    async with SessionLocal() as session:
        await execute_training(session, model_id, scanner_id, symbol, timeframe, history, horizon)


@router.post("/ml/train", status_code=202)
async def train(
    req: TrainRequest, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> dict:
    model_id = uuid4()
    await repo.create_model(
        session, model_id, name=f"{req.scanner_id}:{req.symbol}", version="gb-1", status="training"
    )
    args = (model_id, req.scanner_id, req.symbol.upper(), req.timeframe, req.history, req.horizon)
    enqueued = await enqueue_training(*[str(a) for a in args[:1]] + list(args[1:]))
    if not enqueued:
        background.add_task(_run_inline, *args)
    return {"model_id": str(model_id), "enqueued": enqueued}


@router.get("/ml/models")
async def list_models(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await repo.list_models(session)
    return {
        "items": [
            {
                "model_id": str(r.model_id),
                "name": r.name,
                "version": r.version,
                "status": r.status,
                "metrics": r.metrics,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/ml/models/{model_id}")
async def get_model(model_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    row = await repo.get_model(session, model_id)
    if row is None:
        raise HTTPException(404, "model not found")
    return {
        "model_id": str(row.model_id),
        "name": row.name,
        "version": row.version,
        "status": row.status,
        "report": row.metrics,
        "created_at": row.created_at.isoformat(),
    }
