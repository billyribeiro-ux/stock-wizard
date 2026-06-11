"""Catalyst / flow contracts: insider trades (SEC Form 4 / Finnhub), congressional
trades (Finnhub), earnings events, and news. These feed the catalyst scanners."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import Side


class InsiderTransaction(BaseModel):
    """A corporate-insider transaction (SEC Form 4 / Finnhub insider-transactions)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    insider_name: str
    title: str | None = None
    transaction_date: date
    filing_date: date | None = None
    transaction_code: str | None = Field(
        default=None, description="SEC code: P=buy, S=sell, A=grant, etc."
    )
    side: Side = Side.NEUTRAL
    shares: float = 0.0
    price: Decimal | None = None
    value: Decimal | None = None
    shares_held_after: float | None = None
    source: str = "edgar"


class CongressTrade(BaseModel):
    """A US congressional (House/Senate) trade disclosure (via Finnhub)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    representative: str
    chamber: str | None = Field(default=None, description="house | senate")
    transaction_date: date
    filing_date: date | None = None
    side: Side = Side.NEUTRAL
    amount_low: Decimal | None = None
    amount_high: Decimal | None = None
    asset_name: str | None = None
    source: str = "finnhub"


class EarningsEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    date: date
    hour: str | None = Field(default=None, description="bmo | amc | dmh")
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None
    source: str = "finnhub"


class NewsItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str | None = None
    headline: str
    summary: str | None = None
    url: str | None = None
    published_at: datetime
    category: str | None = None
    source: str = "finnhub"
