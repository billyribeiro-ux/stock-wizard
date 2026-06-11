"""SQLAlchemy 2.0 ORM models.

Time-series tables (ohlcv, internals, option_chains) become TimescaleDB hypertables
via raw SQL in the Alembic migration (ORM ``create_all`` cannot create hypertables).
App-state tables (scan_runs, scanner_results, signals, evidence, vendor_keys, ...) are
regular tables. Full domain objects are stored as JSONB ``payload``/``packet`` columns
with hot fields promoted to typed columns for querying.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Time-series (hypertables)
# --------------------------------------------------------------------------- #
class Ohlcv(Base):
    __tablename__ = "ohlcv"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True, default="yfinance")
    open: Mapped[float] = mapped_column(Numeric(18, 6))
    high: Mapped[float] = mapped_column(Numeric(18, 6))
    low: Mapped[float] = mapped_column(Numeric(18, 6))
    close: Mapped[float] = mapped_column(Numeric(18, 6))
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    vwap: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    is_adjusted: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_flags: Mapped[dict] = mapped_column(JSONB, default=list)


class Internals(Base):
    __tablename__ = "internals"

    metric: Mapped[str] = mapped_column(String(16), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True, default="stub")
    value: Mapped[float] = mapped_column(Float)


class OptionChainRow(Base):
    __tablename__ = "option_chains"

    underlying: Mapped[str] = mapped_column(String(32), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    expiry: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    strike: Mapped[float] = mapped_column(Numeric(18, 6), primary_key=True)
    right: Mapped[str] = mapped_column(String(1), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True, default="yfinance")
    bid: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    ask: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    last: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    open_interest: Mapped[int] = mapped_column(BigInteger, default=0)
    iv: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    gamma: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    vega: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed: Mapped[bool] = mapped_column(Boolean, default=True)


# --------------------------------------------------------------------------- #
# App state (regular tables)
# --------------------------------------------------------------------------- #
class ScanRun(Base):
    __tablename__ = "scan_runs"

    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scanner_id: Mapped[str] = mapped_column(String(64), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    universe: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScannerResultRow(Base):
    __tablename__ = "scanner_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("scan_runs.run_id", ondelete="CASCADE"), index=True
    )
    scanner_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    triggered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    classification: Mapped[str] = mapped_column(String(48))
    levels: Mapped[dict] = mapped_column(JSONB, default=dict)
    payload: Mapped[dict] = mapped_column(JSONB)


class SignalRow(Base):
    __tablename__ = "signals"

    signal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True, nullable=True)
    source_scanner: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    side: Mapped[str] = mapped_column(String(8))
    state: Mapped[str] = mapped_column(String(16), default="PROPOSED", index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    classification: Mapped[str] = mapped_column(String(48))
    entry: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    stop: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    targets: Mapped[list] = mapped_column(JSONB, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    packet: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EvidenceRow(Base):
    __tablename__ = "evidence_packets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    signal_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True, nullable=True)
    result_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True, nullable=True)
    packet: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VendorKey(Base):
    __tablename__ = "vendor_keys"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    vendor: Mapped[str] = mapped_column(String(32), index=True)
    label: Mapped[str] = mapped_column(String(64), default="")
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scopes: Mapped[list] = mapped_column(JSONB, default=list)
    masked: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    model_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32))
    artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="experimental")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    issue: Mapped[str] = mapped_column(String(32))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


HYPERTABLES = {
    "ohlcv": "ts",
    "internals": "ts",
    "option_chains": "as_of",
}
