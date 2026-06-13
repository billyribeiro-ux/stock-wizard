"""Async repository functions — the only place that touches the ORM."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from schemas.models import (
    AlertEventRow,
    AlertRuleRow,
    Backtest,
    EvidenceRow,
    ModelRegistry,
    Ohlcv,
    OptionChainRow,
    ScannerResultRow,
    ScanRun,
    SignalRow,
    VendorKey,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from engine.schemas import OHLCV, ScannerResult, SignalPacket


# ---- market data persistence ----
async def save_ohlcv_bars(session: AsyncSession, ohlcv: OHLCV, cap: int = 5000) -> int:
    """Upsert recent bars into the Timescale hypertable (on-conflict-do-nothing)."""
    bars = ohlcv.bars[-cap:]
    if not bars:
        return 0
    rows = [
        {
            "symbol": b.symbol,
            "timeframe": b.timeframe.value,
            "ts": b.ts,
            "source": b.source,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "vwap": b.vwap,
            "is_adjusted": b.is_adjusted,
            "quality_flags": [f.value for f in b.quality_flags],
        }
        for b in bars
    ]
    stmt = (
        pg_insert(Ohlcv)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["symbol", "timeframe", "ts", "source"])
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def save_option_chain(session: AsyncSession, chain) -> int:
    """Upsert an OptionChain snapshot into the option_chains hypertable."""
    from datetime import datetime as _dt
    from datetime import time as _time

    rows = []
    for c in chain.contracts:
        g = c.greeks
        rows.append(
            {
                "underlying": chain.underlying,
                "as_of": chain.as_of,
                "expiry": _dt.combine(c.expiry, _time(16, 0), tzinfo=UTC),
                "strike": c.strike,
                "right": c.right.value,
                "source": chain.source,
                "bid": c.bid,
                "ask": c.ask,
                "last": c.last,
                "volume": c.volume,
                "open_interest": c.open_interest,
                "iv": c.iv,
                "delta": g.delta if g else None,
                "gamma": g.gamma if g else None,
                "theta": g.theta if g else None,
                "vega": g.vega if g else None,
                "computed": g.computed if g else True,
            }
        )
    if not rows:
        return 0
    stmt = (
        pg_insert(OptionChainRow)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=["underlying", "as_of", "expiry", "strike", "right", "source"]
        )
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def data_health(session: AsyncSession) -> list[dict]:
    """Latest stored bar per (symbol, timeframe) with its age in seconds."""
    stmt = select(Ohlcv.symbol, Ohlcv.timeframe, func.max(Ohlcv.ts).label("last_ts")).group_by(
        Ohlcv.symbol, Ohlcv.timeframe
    )
    rows = (await session.execute(stmt)).all()
    out = []
    for symbol, timeframe, last_ts in rows:
        age = (datetime.now(UTC) - last_ts).total_seconds() if last_ts else None
        out.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "last_bar_age_seconds": int(age) if age is not None else None,
            }
        )
    return out


# ---- scan runs ----
async def create_run(
    session: AsyncSession,
    run_id: UUID,
    scanner_id: str,
    timeframe: str,
    universe: list[str],
    params: dict,
    requested_by: str = "system",
) -> ScanRun:
    run = ScanRun(
        run_id=run_id,
        scanner_id=scanner_id,
        timeframe=timeframe,
        universe=universe,
        params=params,
        status="queued",
        requested_by=requested_by,
    )
    session.add(run)
    await session.commit()
    return run


async def get_run(session: AsyncSession, run_id: UUID) -> ScanRun | None:
    return await session.get(ScanRun, run_id)


async def set_run_status(
    session: AsyncSession, run_id: UUID, status: str, error: str | None = None
) -> None:
    run = await session.get(ScanRun, run_id)
    if run is None:
        return
    run.status = status
    if status in {"done", "error"}:
        run.finished_at = datetime.now(UTC)
    if error:
        run.error = error
    await session.commit()


# ---- results ----
async def save_result(session: AsyncSession, result: ScannerResult) -> None:
    row = ScannerResultRow(
        id=result.id,
        run_id=result.run_id,
        scanner_id=result.scanner_id,
        symbol=result.symbol,
        timeframe=result.timeframe.value,
        ts=result.ts,
        triggered=result.triggered,
        direction=result.direction.value if result.direction else None,
        score=result.score,
        classification=result.classification,
        levels={k: str(v) for k, v in result.levels.items()},
        payload=result.model_dump(mode="json"),
    )
    session.add(row)
    session.add(EvidenceRow(result_id=result.id, packet=result.evidence.model_dump(mode="json")))


async def list_results(session: AsyncSession, run_id: UUID) -> list[dict]:
    stmt = (
        select(ScannerResultRow)
        .where(ScannerResultRow.run_id == run_id)
        .order_by(ScannerResultRow.score.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [r.payload for r in rows]


async def get_result(session: AsyncSession, result_id: UUID) -> dict | None:
    row = await session.get(ScannerResultRow, result_id)
    return row.payload if row else None


# ---- signals ----
async def save_signal(session: AsyncSession, signal: SignalPacket) -> None:
    row = SignalRow(
        signal_id=signal.signal_id,
        run_id=signal.run_id,
        source_scanner=signal.source_scanner,
        symbol=signal.symbol,
        timeframe=signal.timeframe.value,
        side=signal.side.value,
        state=signal.state.value,
        score=signal.score,
        classification=signal.classification,
        entry=signal.entry,
        stop=signal.stop,
        targets=[str(t) for t in signal.targets],
        expires_at=signal.expires_at,
        packet=signal.model_dump(mode="json"),
    )
    session.add(row)


async def list_signals(
    session: AsyncSession, run_id: UUID | None = None, limit: int = 100
) -> list[dict]:
    stmt = select(SignalRow).order_by(SignalRow.created_at.desc()).limit(limit)
    if run_id is not None:
        stmt = stmt.where(SignalRow.run_id == run_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [r.packet for r in rows]


# ---- vendor keys ----
async def list_vendor_keys(session: AsyncSession) -> list[VendorKey]:
    rows = (await session.execute(select(VendorKey).order_by(VendorKey.created_at))).scalars().all()
    return list(rows)


async def get_vendor_key(session: AsyncSession, key_id: UUID) -> VendorKey | None:
    return await session.get(VendorKey, key_id)


async def get_enabled_key_for(session: AsyncSession, vendor: str) -> VendorKey | None:
    stmt = (
        select(VendorKey)
        .where(VendorKey.vendor == vendor, VendorKey.enabled.is_(True))
        .order_by(VendorKey.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def add_vendor_key(
    session: AsyncSession,
    vendor: str,
    label: str,
    ciphertext: bytes,
    masked: str,
    scopes: list[str],
    key_version: int = 1,
) -> VendorKey:
    row = VendorKey(
        vendor=vendor,
        label=label,
        ciphertext=ciphertext,
        masked=masked,
        scopes=scopes,
        key_version=key_version,
        enabled=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def set_vendor_key_enabled(
    session: AsyncSession, key_id: UUID, enabled: bool
) -> VendorKey | None:
    row = await session.get(VendorKey, key_id)
    if row is None:
        return None
    row.enabled = enabled
    await session.commit()
    return row


async def rotate_vendor_key(
    session: AsyncSession, key_id: UUID, ciphertext: bytes, masked: str, key_version: int = 1
) -> VendorKey | None:
    """Replace a key's secret in place (rotate) without losing its label/scopes/id."""
    row = await session.get(VendorKey, key_id)
    if row is None:
        return None
    row.ciphertext = ciphertext
    row.masked = masked
    row.key_version = key_version
    row.last_used_at = None
    await session.commit()
    await session.refresh(row)
    return row


async def update_vendor_key_label(
    session: AsyncSession, key_id: UUID, label: str
) -> VendorKey | None:
    row = await session.get(VendorKey, key_id)
    if row is None:
        return None
    row.label = label
    await session.commit()
    return row


async def delete_vendor_key(session: AsyncSession, key_id: UUID) -> bool:
    row = await session.get(VendorKey, key_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


# ---- backtests ----
async def create_backtest(
    session: AsyncSession,
    backtest_id: UUID,
    scanner_id: str,
    timeframe: str,
    universe: list[str],
    params: dict,
) -> Backtest:
    row = Backtest(
        backtest_id=backtest_id,
        scanner_id=scanner_id,
        timeframe=timeframe,
        universe=universe,
        params=params,
        status="queued",
    )
    session.add(row)
    await session.commit()
    return row


async def get_backtest(session: AsyncSession, backtest_id: UUID) -> Backtest | None:
    return await session.get(Backtest, backtest_id)


async def set_backtest_status(
    session: AsyncSession, backtest_id: UUID, status: str, error: str | None = None
) -> None:
    row = await session.get(Backtest, backtest_id)
    if row is None:
        return
    row.status = status
    if error:
        row.error = error
    if status in {"done", "error"}:
        row.finished_at = datetime.now(UTC)
    await session.commit()


async def save_backtest_result(
    session: AsyncSession, backtest_id: UUID, metrics: dict, payload: dict
) -> None:
    row = await session.get(Backtest, backtest_id)
    if row is None:
        return
    row.metrics = metrics
    row.payload = payload
    row.status = "done"
    row.finished_at = datetime.now(UTC)
    await session.commit()


async def list_backtests(session: AsyncSession, limit: int = 50) -> list[Backtest]:
    stmt = select(Backtest).order_by(Backtest.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


# ---- model registry ----
async def create_model(
    session: AsyncSession, model_id: UUID, name: str, version: str, status: str = "training"
) -> ModelRegistry:
    row = ModelRegistry(model_id=model_id, name=name, version=version, status=status, metrics={})
    session.add(row)
    await session.commit()
    return row


async def save_model_report(
    session: AsyncSession, model_id: UUID, metrics: dict, status: str
) -> None:
    row = await session.get(ModelRegistry, model_id)
    if row is None:
        return
    row.metrics = metrics
    row.status = status
    await session.commit()


async def get_model(session: AsyncSession, model_id: UUID) -> ModelRegistry | None:
    return await session.get(ModelRegistry, model_id)


async def list_models(session: AsyncSession, limit: int = 50) -> list[ModelRegistry]:
    stmt = select(ModelRegistry).order_by(ModelRegistry.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_latest_calibrator(session: AsyncSession, scanner_id: str) -> dict | None:
    """Newest fitted calibrator dict for a scanner (stored in model_registry.metrics)."""
    stmt = (
        select(ModelRegistry)
        .where(ModelRegistry.name == f"calibrator:{scanner_id}")
        .order_by(ModelRegistry.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalars().first()
    if row is None:
        return None
    cal = (row.metrics or {}).get("calibrator")
    return cal if isinstance(cal, dict) and cal.get("fitted") else None


# ---- alert rules / events ----
async def add_alert_rule(session: AsyncSession, rule_id, name, enabled, channel, config) -> None:
    session.add(
        AlertRuleRow(id=rule_id, name=name, enabled=enabled, channel=channel, config=config)
    )
    await session.commit()


async def list_alert_rules(session: AsyncSession, enabled_only: bool = False) -> list[AlertRuleRow]:
    stmt = select(AlertRuleRow).order_by(AlertRuleRow.created_at.desc())
    if enabled_only:
        stmt = stmt.where(AlertRuleRow.enabled.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def get_alert_rule(session: AsyncSession, rule_id) -> AlertRuleRow | None:
    return await session.get(AlertRuleRow, rule_id)


async def set_alert_rule_enabled(
    session: AsyncSession, rule_id, enabled: bool
) -> AlertRuleRow | None:
    row = await session.get(AlertRuleRow, rule_id)
    if row is None:
        return None
    row.enabled = enabled
    row.config = {**row.config, "enabled": enabled}
    await session.commit()
    return row


async def delete_alert_rule(session: AsyncSession, rule_id) -> bool:
    row = await session.get(AlertRuleRow, rule_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def add_alert_event(session: AsyncSession, event) -> None:
    session.add(
        AlertEventRow(
            id=event.id,
            rule_id=event.rule_id,
            signal_id=event.signal_id,
            symbol=event.symbol,
            side=event.side.value,
            scanner_id=event.scanner_id,
            classification=event.classification,
            score=event.score,
            channel=event.channel,
            delivered=event.delivered,
            error=event.error,
            message=event.message,
        )
    )


async def list_alert_events(session: AsyncSession, limit: int = 100) -> list[AlertEventRow]:
    stmt = select(AlertEventRow).order_by(AlertEventRow.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())
