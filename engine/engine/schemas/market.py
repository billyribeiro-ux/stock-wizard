"""Price / OHLCV contracts.

Prices are ``Decimal`` to avoid float drift in level math; timestamps are tz-aware
and stored as UTC (the bar's *open* time). Display-tz conversion happens at the edges.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import AssetClass, BarFlag, Timeframe


class MarketBar(BaseModel):
    """A single OHLCV bar from one source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    timeframe: Timeframe
    ts: datetime = Field(description="Bar open time, tz-aware UTC")
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0)
    vwap: Decimal | None = None
    source: str = "yfinance"
    is_adjusted: bool = False
    quality_flags: list[BarFlag] = Field(default_factory=list)

    @field_validator("ts")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("MarketBar.ts must be timezone-aware (UTC)")
        return v

    @model_validator(mode="after")
    def _ohlc_sane(self) -> MarketBar:
        if self.high < self.low:
            raise ValueError(f"high {self.high} < low {self.low}")
        if not (self.low <= self.open <= self.high):
            raise ValueError("open outside [low, high]")
        if not (self.low <= self.close <= self.high):
            raise ValueError("close outside [low, high]")
        return self

    @property
    def range(self) -> Decimal:
        return self.high - self.low

    @property
    def body(self) -> Decimal:
        return abs(self.close - self.open)

    @property
    def is_up(self) -> bool:
        return self.close >= self.open


class OHLCV(BaseModel):
    """Ordered series of bars for one symbol/timeframe/source."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: Timeframe
    asset_class: AssetClass = AssetClass.EQUITY
    source: str = "yfinance"
    bars: list[MarketBar] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ordered_unique(self) -> OHLCV:
        prev: datetime | None = None
        for bar in self.bars:
            if prev is not None and bar.ts <= prev:
                raise ValueError(f"bars must be strictly increasing in ts (at {bar.ts})")
            prev = bar.ts
        return self

    def __len__(self) -> int:
        return len(self.bars)

    @property
    def closes(self) -> list[Decimal]:
        return [b.close for b in self.bars]

    @property
    def last(self) -> MarketBar | None:
        return self.bars[-1] if self.bars else None
