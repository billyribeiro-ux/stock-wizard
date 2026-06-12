"""Backtest orchestration — fetch history, run the event-driven engine, persist."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from engine.backtesting import BacktestConfig, BacktestEngine
from engine.data import build_ohlcv_source, validate
from engine.schemas import Timeframe

from ..repositories import repo
from .scan_service import _HISTORY_DAYS, _HTF


async def execute_backtest(session, backtest_id: UUID) -> dict:
    bt = await repo.get_backtest(session, backtest_id)
    if bt is None:
        raise ValueError(f"backtest {backtest_id} not found")

    await repo.set_backtest_status(session, backtest_id, "running")
    try:
        timeframe = Timeframe(bt.timeframe)
        days = _HISTORY_DAYS.get(str(bt.params.get("history", "1y")), 366)
        start = datetime.now(UTC) - timedelta(days=days)
        src = build_ohlcv_source("yfinance")
        symbol = bt.universe[0] if bt.universe else "SPY"

        ohlcv = src.get_ohlcv(symbol, timeframe, start)
        ohlcv, _ = validate(ohlcv)
        htf = None
        if bt.scanner_id == "mtf_structure":
            htf = src.get_ohlcv(symbol, _HTF.get(timeframe, Timeframe.D1), start)
            htf, _ = validate(htf)

        cfg = _config_from_params(bt.params)
        result = BacktestEngine(cfg).run(bt.scanner_id, ohlcv, params=bt.params, htf_ohlcv=htf)
        # stamp the symbol onto each trade
        for t in result.trades:
            t.symbol = symbol

        payload = result.model_dump(mode="json")
        await repo.save_backtest_result(
            session, backtest_id, metrics=result.metrics.model_dump(mode="json"), payload=payload
        )
        return payload
    except Exception as exc:
        await repo.set_backtest_status(session, backtest_id, "error", error=str(exc))
        raise


def _config_from_params(params: dict) -> BacktestConfig:
    return BacktestConfig(
        starting_equity=float(params.get("starting_equity", 10_000.0)),
        risk_per_trade=float(params.get("risk_per_trade", 0.01)),
        commission=float(params.get("commission", 0.0)),
        slippage_bps=float(params.get("slippage_bps", 1.0)),
        stop_atr=float(params.get("stop_atr", 1.0)),
        min_score=float(params.get("min_score", 0.4)),
        time_stop_bars=int(params.get("time_stop_bars", 60)),
        allow_short=bool(params.get("allow_short", True)),
    )
