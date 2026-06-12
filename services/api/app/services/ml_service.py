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


async def execute_mining(
    session, model_id: UUID, symbol: str, timeframe: str, history: str, horizon: int
) -> dict:
    """Run the genetic rule miner over the chosen history and persist mined rules."""
    from dataclasses import asdict as _asdict

    from engine.ml import MinerConfig, mine_rules

    days = _HISTORY_DAYS.get(history, 1827)
    start = datetime.now(UTC) - timedelta(days=days)
    src = build_ohlcv_source("yfinance")
    ohlcv = src.get_ohlcv(symbol, Timeframe(timeframe), start)
    ohlcv, _ = validate(ohlcv)

    rules = mine_rules(ohlcv, horizon=horizon, config=MinerConfig())
    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "horizon": horizon,
        "n_rules": len(rules),
        "rules": [{k: v for k, v in _asdict(r).items() if k != "rule"} for r in rules],
    }
    status = "reliable" if any(r.holds_up for r in rules) else "experimental"
    if not rules:
        status = "error"
        payload["error"] = "no profitable rules found (or insufficient history)"
    await repo.save_model_report(session, model_id, payload, status)
    return payload


async def execute_meta(
    session,
    model_id: UUID,
    scanner_id: str,
    symbol: str,
    timeframe: str,
    history: str,
    horizon: int,
) -> dict:
    """Meta-labeling: train a 'should I take this signal' model on the primary's history."""
    from dataclasses import asdict

    from engine.ml import build_meta_model

    days = _HISTORY_DAYS.get(history, 1827)
    start = datetime.now(UTC) - timedelta(days=days)
    ohlcv = build_ohlcv_source("yfinance").get_ohlcv(symbol, Timeframe(timeframe), start)
    ohlcv, _ = validate(ohlcv)

    result = build_meta_model(scanner_id, ohlcv, horizon=horizon)
    payload = {
        "scanner_id": scanner_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "horizon": horizon,
        **asdict(result.report),
    }
    if not result.report.fitted:
        status = "error"
    elif result.report.lift_vs_primary > 0 and result.report.meta_cv_auc > 0.55:
        status = "reliable"
    else:
        status = "experimental"
    await repo.save_model_report(session, model_id, payload, status)
    return payload


async def execute_calibration(
    session,
    model_id: UUID,
    scanner_id: str,
    symbol: str,
    timeframe: str,
    history: str,
    horizon: int,
) -> dict:
    """Fit a confidence calibrator for a scanner and persist it (applied to live signals)."""
    from engine.ml import build_scanner_calibrator

    days = _HISTORY_DAYS.get(history, 1827)
    start = datetime.now(UTC) - timedelta(days=days)
    src = build_ohlcv_source("yfinance")
    ohlcv = src.get_ohlcv(symbol, Timeframe(timeframe), start)
    ohlcv, _ = validate(ohlcv)

    cal = build_scanner_calibrator(scanner_id, ohlcv, horizon=horizon)
    payload = {
        "scanner_id": scanner_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "horizon": horizon,
        "calibrator": cal.to_dict(),
        "n_samples": cal.n_samples,
        "base_rate": cal.base_rate,
        "brier_raw": cal.brier_raw,
        "brier_calibrated": cal.brier_calibrated,
        "improved": cal.fitted and cal.brier_calibrated < cal.brier_raw,
    }
    status = "reliable" if payload["improved"] else ("experimental" if cal.fitted else "error")
    await repo.save_model_report(session, model_id, payload, status)
    return payload


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
