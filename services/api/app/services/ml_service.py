"""ML training orchestration — fetch history, train a setup-success model, persist."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from engine.data import build_ohlcv_source, validate
from engine.ml import train_setup_model
from engine.schemas import Timeframe

from ..repositories import repo
from .scan_service import _HISTORY_DAYS


async def execute_training(
    session,
    model_id: UUID,
    scanner_id: str,
    symbol: str,
    timeframe: str,
    history: str,
    horizon: int,
) -> dict:
    days = _HISTORY_DAYS.get(history, 1827)
    start = datetime.now(UTC) - timedelta(days=days)
    src = build_ohlcv_source("yfinance")
    ohlcv = src.get_ohlcv(symbol, Timeframe(timeframe), start)
    ohlcv, _ = validate(ohlcv)

    report = train_setup_model(ohlcv, scanner_id=scanner_id, horizon=horizon)
    if report is None:
        await repo.save_model_report(session, model_id, {"error": "insufficient data"}, "error")
        return {"status": "error"}

    payload = asdict(report)
    payload["symbol"] = symbol
    payload["timeframe"] = timeframe
    status = "reliable" if report.reliable else "experimental"
    await repo.save_model_report(session, model_id, payload, status)
    return payload
