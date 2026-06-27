"""Adapter-driven data layer.

Every vendor plugs in behind small capability Protocols so the engine can compare
evidence across sources. yfinance is the free default; paid/keyed vendors (Finnhub,
Polygon, Tradier, Theta, ORATS, CBOE) and the keyless SEC EDGAR plug in via the
registry and the Settings API-key panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from ..schemas import (
    OHLCV,
    CongressTrade,
    EarningsEvent,
    InsiderTransaction,
    NewsItem,
    OptionChain,
    Timeframe,
)


class DataSourceError(RuntimeError):
    """Raised when an adapter cannot satisfy a request (network, parsing, shape)."""


class MissingCredentials(DataSourceError):
    """Raised when a keyed vendor is used without a configured API key."""


class Capability:
    OHLCV = "ohlcv"
    OPTIONS = "options"
    INSIDER = "insider"
    CONGRESS = "congress"
    EARNINGS = "earnings"
    NEWS = "news"
    INTERNALS = "internals"


@dataclass(frozen=True)
class VendorInfo:
    """Static metadata about a vendor, surfaced to the Settings panel."""

    vendor: str
    label: str
    requires_key: bool
    capabilities: list[str]
    docs_url: str = ""
    notes: str = ""


@runtime_checkable
class OhlcvSource(Protocol):
    name: str

    def get_ohlcv(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime | None = None
    ) -> OHLCV: ...


@runtime_checkable
class OptionSource(Protocol):
    name: str

    def get_option_chain(self, underlying: str, expiry: date | None = None) -> OptionChain: ...


@runtime_checkable
class InsiderSource(Protocol):
    name: str

    def get_insider_transactions(
        self, symbol: str, since: date | None = None
    ) -> list[InsiderTransaction]: ...


@runtime_checkable
class CongressSource(Protocol):
    name: str

    def get_congress_trades(
        self, symbol: str, since: date | None = None
    ) -> list[CongressTrade]: ...


@runtime_checkable
class EarningsSource(Protocol):
    name: str

    def get_earnings(self, symbol: str, since: date | None = None) -> list[EarningsEvent]: ...


@runtime_checkable
class NewsSource(Protocol):
    name: str

    def get_news(self, symbol: str, since: date | None = None) -> list[NewsItem]: ...


@dataclass
class InternalsBar:
    metric: str
    ts: datetime
    value: float
    source: str = "stub"


@runtime_checkable
class InternalsSource(Protocol):
    def get_internals(
        self, metric: str, start: datetime, end: datetime | None = None
    ) -> list[InternalsBar]: ...


@dataclass
class SourceContext:
    """Optional per-call context (decrypted vendor key, settings)."""

    api_key: str | None = None
    extra: dict = field(default_factory=dict)
