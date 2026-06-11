"""Options / greeks / chain contracts.

yfinance does not supply greeks, so ``Greeks.computed=True`` flags values we solved
ourselves via Black-Scholes. IV may likewise be solved from mid-price.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import OptionRight


class Greeks(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float = 0.0
    iv: float
    computed: bool = Field(
        default=True, description="True when we solved these (e.g. from yfinance chain)"
    )


class OptionContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    underlying: str
    expiry: date
    strike: Decimal
    right: OptionRight
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal | None = None
    volume: int = Field(default=0, ge=0)
    open_interest: int = Field(default=0, ge=0)
    iv: float | None = None
    greeks: Greeks | None = None
    multiplier: int = 100
    as_of: datetime

    @property
    def mid(self) -> Decimal | None:
        if self.bid is not None and self.ask is not None and self.ask >= self.bid:
            return (self.bid + self.ask) / 2
        return self.last


class OptionChain(BaseModel):
    """Snapshot of an underlying's option chain at ``as_of``."""

    model_config = ConfigDict(extra="forbid")

    underlying: str
    as_of: datetime
    spot: Decimal
    risk_free_rate: float = 0.0525
    contracts: list[OptionContract] = Field(default_factory=list)
    source: str = "yfinance"
    degraded: bool = Field(
        default=False, description="True when data quality is poor (missing OI/quotes/IV)"
    )

    @property
    def expiries(self) -> list[date]:
        return sorted({c.expiry for c in self.contracts})

    def for_expiry(self, expiry: date) -> list[OptionContract]:
        return [c for c in self.contracts if c.expiry == expiry]

    def calls(self) -> list[OptionContract]:
        return [c for c in self.contracts if c.right == OptionRight.CALL]

    def puts(self) -> list[OptionContract]:
        return [c for c in self.contracts if c.right == OptionRight.PUT]
