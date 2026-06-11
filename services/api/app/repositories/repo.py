"""Async repository functions — the only place that touches the ORM."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from schemas.models import (
    EvidenceRow,
    ScannerResultRow,
    ScanRun,
    SignalRow,
    VendorKey,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.schemas import ScannerResult, SignalPacket


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


async def delete_vendor_key(session: AsyncSession, key_id: UUID) -> bool:
    row = await session.get(VendorKey, key_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True
