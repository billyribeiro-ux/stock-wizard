"""Canonical Pydantic v2 contracts — the single source of truth for data shapes
shared across the engine, API, worker, and (via generated JSON Schema) the dashboard.
"""

from __future__ import annotations

from .backtest import (
    BacktestMetrics,
    BacktestResult,
    EquityPoint,
    TradeRecord,
)
from .catalyst import (
    CongressTrade,
    EarningsEvent,
    InsiderTransaction,
    NewsItem,
)
from .enums import (
    AssetClass,
    BarFlag,
    EvidenceKind,
    GexConvention,
    OptionRight,
    Regime,
    ReportFormat,
    ReportKind,
    Side,
    SignalState,
    Timeframe,
    TradeStyle,
)
from .evidence import (
    Analog,
    EvidenceItem,
    EvidencePacket,
    InvalidationRule,
)
from .features import FeatureSnapshot
from .market import OHLCV, MarketBar
from .options import Greeks, OptionChain, OptionContract
from .report import ReportSpec
from .scanner import ScannerResult, ScannerSpec
from .signal import SCHEMA_VERSION, SignalPacket

__all__ = [
    # enums
    "AssetClass",
    "BarFlag",
    "EvidenceKind",
    "GexConvention",
    "OptionRight",
    "Regime",
    "ReportFormat",
    "ReportKind",
    "Side",
    "SignalState",
    "Timeframe",
    "TradeStyle",
    # market
    "MarketBar",
    "OHLCV",
    # options
    "Greeks",
    "OptionContract",
    "OptionChain",
    # features
    "FeatureSnapshot",
    # evidence
    "Analog",
    "EvidenceItem",
    "EvidencePacket",
    "InvalidationRule",
    # scanner
    "ScannerResult",
    "ScannerSpec",
    # signal
    "SignalPacket",
    "SCHEMA_VERSION",
    # backtest
    "BacktestMetrics",
    "BacktestResult",
    "EquityPoint",
    "TradeRecord",
    # report
    "ReportSpec",
    # catalyst / flow
    "InsiderTransaction",
    "CongressTrade",
    "EarningsEvent",
    "NewsItem",
]
