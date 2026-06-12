"""Scanner base: a uniform contract so every scanner is standalone-testable,
exportable, and explainable, and can feed the signal engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ..schemas import (
    OHLCV,
    CongressTrade,
    FeatureSnapshot,
    InsiderTransaction,
    OptionChain,
    ScannerResult,
    ScannerSpec,
    Timeframe,
)


@dataclass
class ScanContext:
    """Everything a scanner might need. Each scanner reads only what it uses."""

    symbol: str
    timeframe: Timeframe
    snapshot: FeatureSnapshot
    ohlcv: OHLCV | None = None
    htf_ohlcv: OHLCV | None = None
    chain: OptionChain | None = None
    insider: list[InsiderTransaction] = field(default_factory=list)
    congress: list[CongressTrade] = field(default_factory=list)
    aux: dict[str, OHLCV] = field(default_factory=dict)  # cross-asset peers (^VIX, SPY, ...)
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    run_id: UUID | None = None
    params: dict[str, Any] = field(default_factory=dict)


class Scanner(ABC):
    scanner_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    default_params: dict[str, Any] = {}
    params_schema: dict[str, Any] = {}

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = {**self.default_params, **(params or {})}

    @classmethod
    def spec(cls) -> ScannerSpec:
        return ScannerSpec(
            scanner_id=cls.scanner_id,
            name=cls.name,
            description=cls.description,
            category=cls.category,
            params_schema=cls.params_schema,
            default_params=cls.default_params,
        )

    @abstractmethod
    def run(self, ctx: ScanContext) -> ScannerResult:
        """Evaluate the scanner and return a ScannerResult with an EvidencePacket."""

    # shared helper for subclasses
    def _p(self, key: str, ctx: ScanContext) -> Any:
        return ctx.params.get(key, self.params.get(key))
