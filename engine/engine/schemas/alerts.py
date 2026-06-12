"""Alerting contracts: user-defined alert rules and the events they emit.

An alert rule matches signals (by scanner, side, score, symbol, classification) and
dispatches to a channel. This is the "buy/sell signal alerts" delivery layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import Side


class AlertChannel:
    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"


class AlertRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    name: str
    enabled: bool = True
    scanner_ids: list[str] = Field(default_factory=list, description="Empty = any scanner")
    symbols: list[str] = Field(default_factory=list, description="Empty = any symbol")
    sides: list[Side] = Field(default_factory=list, description="Empty = any side")
    classifications: list[str] = Field(
        default_factory=list, description="Empty = any classification"
    )
    min_score: float = Field(default=0.6, ge=0.0, le=1.0)
    channel: str = AlertChannel.LOG
    target: str = Field(default="", description="Webhook URL / email address (channel-specific)")
    cooldown_seconds: int = Field(
        default=0, ge=0, description="Min seconds between fires per symbol"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AlertEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    rule_name: str
    signal_id: UUID
    symbol: str
    side: Side
    scanner_id: str
    classification: str
    score: float
    channel: str
    delivered: bool = False
    error: str | None = None
    message: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
