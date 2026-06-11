"""Canonical enumerations shared across every contract.

Keeping these in one module guarantees the engine, API, worker, and (via generated
JSON Schema) the SvelteKit dashboard all speak the same vocabulary.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String-valued enum that serializes to its value (3.11-friendly)."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class Timeframe(StrEnum):
    """Bar granularities. Values match common vendor strings."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1wk"
    MO1 = "1mo"

    @property
    def seconds(self) -> int:
        return {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1wk": 604800,
            "1mo": 2592000,
        }[self.value]

    @property
    def is_intraday(self) -> bool:
        return self.seconds < 86400


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    FUTURE = "future"
    OPTION = "option"
    CRYPTO = "crypto"
    FX = "fx"


class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

    @property
    def sign(self) -> int:
        return {"LONG": 1, "SHORT": -1, "NEUTRAL": 0}[self.value]


class OptionRight(StrEnum):
    CALL = "C"
    PUT = "P"


class SignalState(StrEnum):
    """Lifecycle of a signal from proposal to terminal state."""

    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    FILLED = "FILLED"


class Regime(StrEnum):
    """Coarse market regime tag attached to features/signals."""

    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    POSITIVE_GAMMA = "positive_gamma"
    NEGATIVE_GAMMA = "negative_gamma"
    UNKNOWN = "unknown"


class BarFlag(StrEnum):
    """Data-quality annotations attached to a bar by the validator."""

    GAP = "GAP"
    SPLIT_SUSPECT = "SPLIT_SUSPECT"
    ZERO_VOLUME = "ZERO_VOLUME"
    OUT_OF_HOURS = "OUT_OF_HOURS"
    IMPOSSIBLE = "IMPOSSIBLE"
    DUPLICATE = "DUPLICATE"


class TradeStyle(StrEnum):
    SCALP = "scalp"
    INTRADAY = "intraday"
    SWING = "swing"
    POSITION = "position"
    INVESTMENT = "investment"


class ReportKind(StrEnum):
    SCANNER_RESULTS = "scanner_results"
    SIGNAL = "signal"
    BACKTEST = "backtest"
    FORWARD_TEST = "forward_test"
    EVIDENCE = "evidence"


class ReportFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"


class EvidenceKind(StrEnum):
    FEATURE = "feature"
    LEVEL = "level"
    PATTERN = "pattern"
    INTERNAL = "internal"
    OPTIONS = "options"
    VOLUME = "volume"
    CATALYST = "catalyst"
    TIME = "time"
    DATA_QUALITY = "data_quality"


class GexConvention(StrEnum):
    """Dealer-gamma sign convention for GEX computation."""

    DEALER_LONG_CALLS = "dealer_long_calls"  # calls +, puts - (most common)
    ABSOLUTE = "absolute"  # |gamma|*oi, no sign
