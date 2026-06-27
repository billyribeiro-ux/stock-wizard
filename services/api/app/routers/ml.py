"""ML / self-learning endpoints: train setup-success models, list, inspect."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from engine.scanners import list_scanner_ids

from ..db import SessionLocal, get_session
from ..jobs import enqueue_training
from ..repositories import repo
from ..security import require_token
from ..services.ml_service import (
    execute_calibration,
    execute_meta,
    execute_mining,
    execute_training,
)

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
    enqueued = await enqueue_training(
        str(model_id), req.scanner_id, req.symbol.upper(), req.timeframe, req.history, req.horizon
    )
    if not enqueued:
        background.add_task(_run_inline, *args)
    return {"model_id": str(model_id), "enqueued": enqueued}


class MineRequest(BaseModel):
    symbol: str
    timeframe: str = "1d"
    history: str = "5y"
    horizon: int = Field(default=10, ge=1, le=120)


async def _mine_inline(model_id, symbol, timeframe, history, horizon) -> None:
    async with SessionLocal() as session:
        await execute_mining(session, model_id, symbol, timeframe, history, horizon)


@router.post("/ml/mine", status_code=202)
async def mine(
    req: MineRequest, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> dict:
    """Genetic rule miner: evolve human-readable rules, walk-forward validated."""
    model_id = uuid4()
    await repo.create_model(
        session, model_id, name=f"genetic:{req.symbol.upper()}", version="ga-1", status="training"
    )
    background.add_task(
        _mine_inline, model_id, req.symbol.upper(), req.timeframe, req.history, req.horizon
    )
    return {"model_id": str(model_id), "enqueued": False}


class CalibrateRequest(BaseModel):
    scanner_id: str
    symbol: str
    timeframe: str = "1d"
    history: str = "5y"
    horizon: int = Field(default=10, ge=1, le=120)


async def _calibrate_inline(model_id, scanner_id, symbol, timeframe, history, horizon) -> None:
    async with SessionLocal() as session:
        await execute_calibration(
            session, model_id, scanner_id, symbol, timeframe, history, horizon
        )


@router.post("/ml/calibrate", status_code=202)
async def calibrate(
    req: CalibrateRequest, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> dict:
    """Fit + persist a confidence calibrator so this scanner's score == real win-rate."""
    if req.scanner_id not in list_scanner_ids():
        raise HTTPException(404, f"unknown scanner_id: {req.scanner_id}")
    model_id = uuid4()
    await repo.create_model(
        session, model_id, name=f"calibrator:{req.scanner_id}", version="iso-1", status="training"
    )
    background.add_task(
        _calibrate_inline,
        model_id,
        req.scanner_id,
        req.symbol.upper(),
        req.timeframe,
        req.history,
        req.horizon,
    )
    return {"model_id": str(model_id), "enqueued": False}


class MetaRequest(BaseModel):
    scanner_id: str
    symbol: str
    timeframe: str = "1d"
    history: str = "5y"
    horizon: int = Field(default=10, ge=1, le=120)


async def _meta_inline(model_id, scanner_id, symbol, timeframe, history, horizon) -> None:
    async with SessionLocal() as session:
        await execute_meta(session, model_id, scanner_id, symbol, timeframe, history, horizon)


@router.post("/ml/meta", status_code=202)
async def meta(
    req: MetaRequest, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
) -> dict:
    """Meta-labeling: learn whether to act on a scanner's primary signal (+ sizing edge)."""
    if req.scanner_id not in list_scanner_ids():
        raise HTTPException(404, f"unknown scanner_id: {req.scanner_id}")
    model_id = uuid4()
    await repo.create_model(
        session, model_id, name=f"meta:{req.scanner_id}", version="ml-1", status="training"
    )
    background.add_task(
        _meta_inline,
        model_id,
        req.scanner_id,
        req.symbol.upper(),
        req.timeframe,
        req.history,
        req.horizon,
    )
    return {"model_id": str(model_id), "enqueued": False}


@router.get("/ml/leakage-audit")
async def leakage_audit(symbol: str, timeframe: str = "1d", history: str = "2y") -> dict:
    """Prove the feature pipeline is as-of-safe for this symbol (no lookahead)."""
    from dataclasses import asdict
    from datetime import UTC, datetime, timedelta

    from engine.backtesting import audit_feature_lookahead
    from engine.data import build_ohlcv_source, validate
    from engine.schemas import Timeframe

    from ..services.scan_service import _HISTORY_DAYS

    start = datetime.now(UTC) - timedelta(days=_HISTORY_DAYS.get(history, 731))
    ohlcv, _ = validate(
        build_ohlcv_source("yfinance").get_ohlcv(symbol.upper(), Timeframe(timeframe), start)
    )
    report = audit_feature_lookahead(ohlcv)
    if report is None:
        raise HTTPException(422, "insufficient history for a leakage audit")
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        **asdict(report),
        "summary": report.summary,
    }


@router.get("/ml/feature-info")
async def feature_info(
    symbol: str, timeframe: str = "1d", history: str = "5y", horizon: int = 10
) -> dict:
    """Information-theoretic feature ranking: mutual information with the forward outcome."""
    from dataclasses import asdict
    from datetime import UTC, datetime, timedelta

    from engine.data import build_ohlcv_source, validate
    from engine.ml import mutual_information_ranking
    from engine.schemas import Timeframe

    from ..services.scan_service import _HISTORY_DAYS

    start = datetime.now(UTC) - timedelta(days=_HISTORY_DAYS.get(history, 1827))
    ohlcv, _ = validate(
        build_ohlcv_source("yfinance").get_ohlcv(symbol.upper(), Timeframe(timeframe), start)
    )
    report = mutual_information_ranking(ohlcv, horizon=horizon)
    if report is None:
        raise HTTPException(422, "insufficient history for a feature-info analysis")
    return {"symbol": symbol.upper(), "timeframe": timeframe, **asdict(report)}


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
