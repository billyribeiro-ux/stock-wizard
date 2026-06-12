"""Scan orchestration — the shared path used by both the API (inline fallback) and
the worker. Resolves data sources, builds features, runs the scanner, persists results
and signals, and publishes signals to Redis for the live stream.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import redis.asyncio as aioredis

from engine.data import build_ohlcv_source, build_option_source, validate
from engine.data.registry import build_congress_source, build_insider_source
from engine.features import FeatureFactory
from engine.scanners import build_scanner
from engine.scanners.base import ScanContext
from engine.schemas import AssetClass, Timeframe
from engine.signals import build_signal

from ..pubsub import publish_signal, signal_channel  # noqa: F401
from ..repositories import repo

_HISTORY_DAYS = {
    "5d": 5,
    "1mo": 31,
    "3mo": 93,
    "6mo": 186,
    "1y": 366,
    "2y": 731,
    "5y": 1827,
    "10y": 3653,
    "20y": 7305,
    "30y": 10958,
}
_HTF = {
    Timeframe.M1: Timeframe.M15,
    Timeframe.M5: Timeframe.H1,
    Timeframe.M15: Timeframe.H1,
    Timeframe.M30: Timeframe.D1,
    Timeframe.H1: Timeframe.D1,
    Timeframe.H4: Timeframe.D1,
    Timeframe.D1: Timeframe.W1,
    Timeframe.W1: Timeframe.MO1,
    Timeframe.MO1: Timeframe.MO1,
}
_NEEDS_OPTIONS = {"spx_gamma_command"}
_NEEDS_FLOW = {"insider_congress_flow"}
_NEEDS_EARNINGS = {"earnings_guidance"}
_NEEDS_AUX = {
    "vix_tail_risk",
    "index_divergence",
    "cross_asset_risk",
    "sector_rotation",
    "macro_regime",
}
_AUX_SYMBOLS = ["^VIX", "SPY", "QQQ", "TLT"]
_SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC"]


def _start_for(history: str) -> datetime:
    days = _HISTORY_DAYS.get(history, 186)
    return datetime.now(UTC) - timedelta(days=days)


async def execute_scan(session, run_id: UUID, redis: aioredis.Redis | None = None) -> int:
    """Run a previously-created ScanRun. Returns the number of triggered results."""
    run = await repo.get_run(session, run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")

    await repo.set_run_status(session, run_id, "running")
    triggered = 0
    try:
        timeframe = Timeframe(run.timeframe)
        start = _start_for(str(run.params.get("history", "6mo")))
        ohlcv_src = build_ohlcv_source("yfinance")
        opt_src = build_option_source("yfinance") if run.scanner_id in _NEEDS_OPTIONS else None
        factory = FeatureFactory()

        aux: dict = {}
        if run.scanner_id in _NEEDS_AUX:
            peers = _SECTOR_ETFS if run.scanner_id == "sector_rotation" else _AUX_SYMBOLS
            for peer in peers:
                try:
                    peer_ohlcv, _ = validate(ohlcv_src.get_ohlcv(peer, timeframe, start))
                    if len(peer_ohlcv) > 0:
                        aux[peer] = peer_ohlcv
                except Exception:
                    continue

        for symbol in run.universe:
            ohlcv = ohlcv_src.get_ohlcv(symbol, timeframe, start)
            ohlcv, _ = validate(ohlcv)
            if len(ohlcv) == 0:
                continue
            with contextlib.suppress(Exception):  # best-effort persistence (powers data-health)
                await repo.save_ohlcv_bars(session, ohlcv)

            htf = None
            if run.scanner_id == "mtf_structure":
                htf = ohlcv_src.get_ohlcv(symbol, _HTF.get(timeframe, Timeframe.D1), start)
                htf, _ = validate(htf)

            chain = None
            if opt_src is not None:
                underlying = run.params.get("underlying", symbol)
                chain = opt_src.get_option_chain(underlying)

            insider, congress = [], []
            if run.scanner_id in _NEEDS_FLOW:
                insider, congress = await _fetch_flow(session, symbol)
            earnings = []
            if run.scanner_id in _NEEDS_EARNINGS:
                earnings = await _fetch_earnings(session, symbol)

            snapshot = factory.build_snapshot(ohlcv, chain=chain)
            scanner = build_scanner(run.scanner_id, run.params)
            ctx = ScanContext(
                symbol=symbol,
                timeframe=timeframe,
                snapshot=snapshot,
                ohlcv=ohlcv,
                htf_ohlcv=htf,
                chain=chain,
                insider=insider,
                congress=congress,
                earnings=earnings,
                aux=aux,
                run_id=run_id,
            )
            result = scanner.run(ctx)
            await repo.save_result(session, result)

            signal = build_signal(result, snapshot, asset_class=_asset_class(symbol))
            await repo.save_signal(session, signal)
            if result.triggered:
                triggered += 1
                if redis is not None:
                    await publish_signal(redis, str(run_id), signal.model_dump_json())
                with contextlib.suppress(Exception):  # alerts are best-effort
                    from .alert_service import evaluate_alerts

                    await evaluate_alerts(session, signal)

        await session.commit()
        await repo.set_run_status(session, run_id, "done")
    except Exception as exc:
        await repo.set_run_status(session, run_id, "error", error=str(exc))
        raise
    return triggered


async def _fetch_flow(session, symbol: str):
    """Fetch insider (EDGAR, keyless) + congress (Finnhub, keyed) flow, best-effort."""
    insider, congress = [], []
    try:
        insider = build_insider_source("sec_edgar").get_insider_transactions(symbol)
    except Exception:
        insider = []
    key_row = await repo.get_enabled_key_for(session, "finnhub")
    if key_row is not None:
        from ..security import get_secret_box

        try:
            api_key = get_secret_box().decrypt(key_row.ciphertext)
            congress = build_congress_source("finnhub", api_key).get_congress_trades(symbol)
        except Exception:
            congress = []
    return insider, congress


async def _fetch_earnings(session, symbol: str):
    """Fetch earnings calendar via Finnhub (keyed), best-effort."""
    key_row = await repo.get_enabled_key_for(session, "finnhub")
    if key_row is None:
        return []
    from engine.data.finnhub_source import FinnhubSource

    from ..security import get_secret_box

    try:
        api_key = get_secret_box().decrypt(key_row.ciphertext)
        return FinnhubSource(api_key).get_earnings(symbol)
    except Exception:
        return []


def _asset_class(symbol: str) -> AssetClass:
    if symbol.upper() in {"SPY", "QQQ", "IWM", "DIA"}:
        return AssetClass.ETF
    if symbol.startswith("^"):
        return AssetClass.INDEX
    return AssetClass.EQUITY
