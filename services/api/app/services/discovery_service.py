"""Self-learning discovery orchestration — fetch the chosen lookback of history,
replay it, self-identify buy/sell reasons, persist the report."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from engine.data import build_ohlcv_source, validate
from engine.ml import discover
from engine.schemas import Timeframe

from ..repositories import repo
from .scan_service import _HISTORY_DAYS

DISCOVERY_SCANNER_ID = "self_discovery"


async def execute_discovery(session, discovery_id: UUID) -> dict:
    row = await repo.get_backtest(session, discovery_id)
    if row is None:
        raise ValueError(f"discovery {discovery_id} not found")

    await repo.set_backtest_status(session, discovery_id, "running")
    try:
        timeframe = Timeframe(row.timeframe)
        days = _HISTORY_DAYS.get(str(row.params.get("history", "1y")), 366)
        start = datetime.now(UTC) - timedelta(days=days)
        symbol = row.universe[0] if row.universe else "SPY"

        src = build_ohlcv_source("yfinance")
        ohlcv = src.get_ohlcv(symbol, timeframe, start)
        ohlcv, _ = validate(ohlcv)

        report = discover(
            ohlcv,
            swing_k=int(row.params.get("swing_k", 3)),
            min_move_atr=float(row.params.get("min_move_atr", 1.5)),
        )
        if report is None:
            await repo.set_backtest_status(
                session, discovery_id, "error", error="insufficient history for discovery"
            )
            return {"status": "error"}

        payload = asdict(report)
        metrics = {
            "n_events": report.n_events,
            "n_bought": report.n_bought,
            "n_sold": report.n_sold,
            "n_bars": report.n_bars,
            "trade_style": report.trade_style,
        }
        await repo.save_backtest_result(session, discovery_id, metrics=metrics, payload=payload)
        return payload
    except Exception as exc:
        await repo.set_backtest_status(session, discovery_id, "error", error=str(exc))
        raise
