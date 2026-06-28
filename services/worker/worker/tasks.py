"""Worker task implementations."""

from __future__ import annotations

from uuid import UUID

from app.db import SessionLocal
from app.pubsub import get_redis
from app.services.backtest_service import execute_backtest
from app.services.discovery_service import execute_discovery
from app.services.ml_service import execute_training
from app.services.roster_service import validate_roster
from app.services.scan_service import execute_scan


async def run_scan(ctx, run_id: str) -> int:
    """Execute a scan run end-to-end and publish triggered signals."""
    redis = get_redis()
    async with SessionLocal() as session:
        try:
            return await execute_scan(session, UUID(run_id), redis=redis)
        finally:
            await redis.aclose()


async def run_backtest(ctx, backtest_id: str) -> int:
    """Execute a backtest end-to-end and persist results."""
    async with SessionLocal() as session:
        result = await execute_backtest(session, UUID(backtest_id))
        return result.get("metrics", {}).get("total_trades", 0)


async def run_discovery(ctx, discovery_id: str) -> int:
    """Run self-learning discovery over past history and persist the report."""
    async with SessionLocal() as session:
        payload = await execute_discovery(session, UUID(discovery_id))
        return payload.get("n_events", 0) if isinstance(payload, dict) else 0


async def train_model(
    ctx, model_id: str, scanner_id: str, symbol: str, timeframe: str, history: str, horizon: int
) -> str:
    """Train a setup-success model and persist the report."""
    async with SessionLocal() as session:
        report = await execute_training(
            session, UUID(model_id), scanner_id, symbol, timeframe, history, int(horizon)
        )
        return report.get("status", "done") if isinstance(report, dict) else "done"


async def run_roster_validation(ctx) -> int:
    """Re-validate the scanner roster (forward-test the basket, persist blended OOS edge
    weights). Scheduled periodically so edge weights stay fresh as regimes shift."""
    async with SessionLocal() as session:
        report = await validate_roster(session)
        return int(report.get("n_scanners", 0))
