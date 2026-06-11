"""Backtest result contracts. (Full engine lands in a later phase; the contract is
locked now so reports/UI can be built against it.)"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import Side


class TradeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: Side
    entry_ts: datetime
    entry_price: Decimal
    exit_ts: datetime | None = None
    exit_price: Decimal | None = None
    pnl: Decimal | None = None
    return_pct: float | None = None
    mfe: float | None = Field(default=None, description="Max favorable excursion")
    mae: float | None = Field(default=None, description="Max adverse excursion")
    hold_seconds: int | None = None
    exit_reason: str | None = None


class EquityPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ts: datetime
    equity: Decimal
    drawdown: float = 0.0


class BacktestMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    total_pnl: Decimal = Decimal(0)
    cagr: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    recovery_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_rr: float = 0.0
    exposure: float = 0.0


class BacktestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backtest_id: UUID = Field(default_factory=uuid4)
    scanner_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    universe: list[str] = Field(default_factory=list)
    period_start: date
    period_end: date
    trades: list[TradeRecord] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    metrics: BacktestMetrics = Field(default_factory=BacktestMetrics)
    regime_breakdown: dict[str, BacktestMetrics] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
