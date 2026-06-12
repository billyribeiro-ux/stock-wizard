"""The universal SignalPacket — the most important contract in the system.

A signal carries identity, instrument, direction & conviction, a full trade plan,
context (levels + features + evidence), a lifecycle state, and provenance (which
fields we computed vs sourced). Everything downstream (UI, exports, backtests,
forward tests, ML) keys off this object.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import AssetClass, Regime, Side, SignalState, Timeframe, TradeStyle
from .evidence import EvidencePacket
from .features import FeatureSnapshot

SCHEMA_VERSION = "1.0.0"


class SignalPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # --- identity ---
    signal_id: UUID = Field(default_factory=uuid4)
    run_id: UUID | None = None
    source_scanner: str
    schema_version: str = SCHEMA_VERSION
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # --- instrument ---
    symbol: str
    asset_class: AssetClass
    timeframe: Timeframe
    as_of: datetime

    # --- direction & conviction ---
    side: Side
    state: SignalState = SignalState.PROPOSED
    trade_style: TradeStyle = TradeStyle.INTRADAY
    score: float = Field(ge=0.0, le=1.0)
    calibrated_probability: float | None = Field(
        default=None, description="Score remapped to the historical win-rate (isotonic), if fit"
    )
    confidence_band: tuple[float, float] = (0.0, 1.0)
    regime: Regime = Regime.UNKNOWN

    # --- trade plan ---
    entry: Decimal | None = None
    stop: Decimal | None = None
    targets: list[Decimal] = Field(default_factory=list)
    rr: float | None = Field(default=None, description="Reward/risk to first target")
    suggested_size: Decimal | None = None
    time_stop: datetime | None = None
    expires_at: datetime | None = None

    # --- context ---
    classification: str = ""
    key_levels: dict[str, Decimal] = Field(default_factory=dict)
    features: FeatureSnapshot | None = None
    evidence: EvidencePacket

    # --- provenance ---
    data_sources: list[str] = Field(default_factory=list)
    computed_fields: list[str] = Field(
        default_factory=list, description="Which greeks/IV/etc. were solved, not sourced"
    )
    linked_signals: list[UUID] = Field(default_factory=list)
    notes: str | None = None
