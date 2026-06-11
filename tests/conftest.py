"""Shared test fixtures: synthetic OHLCV and option chains (no network)."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from engine.schemas import (
    OHLCV,
    MarketBar,
    OptionChain,
    OptionContract,
    OptionRight,
    Timeframe,
)


def make_ohlcv(
    symbol: str = "SPY",
    n: int = 160,
    start_px: float = 100.0,
    timeframe: Timeframe = Timeframe.M5,
    drift: float = 0.15,
    amp: float = 0.8,
    base_volume: int = 100_000,
) -> OHLCV:
    """Zig-zag trending series so swing pivots exist."""
    bars: list[MarketBar] = []
    base = datetime(2026, 6, 10, 13, 30, tzinfo=UTC)
    for i in range(n):
        px = start_px + drift * i + amp * math.sin(i / 4.0)
        bars.append(
            MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                ts=base + timedelta(seconds=timeframe.seconds * i),
                open=Decimal(str(round(px - 0.05, 2))),
                high=Decimal(str(round(px + 0.25, 2))),
                low=Decimal(str(round(px - 0.25, 2))),
                close=Decimal(str(round(px, 2))),
                volume=base_volume + (i % 5) * 40_000,
            )
        )
    return OHLCV(symbol=symbol, timeframe=timeframe, source="test", bars=bars)


def make_chain(
    underlying: str = "SPY",
    spot: float = 124.0,
    call_wall_offset: int = 5,
    put_wall_offset: int = -5,
    iv: float = 0.18,
    width: int = 15,
) -> OptionChain:
    """Chain with a heavy call strike above and heavy put strike below spot."""
    now = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)
    contracts: list[OptionContract] = []
    s = round(spot)
    for k in range(s - width, s + width + 1):
        coi = 2500 if k == s + call_wall_offset else 500
        poi = 2500 if k == s + put_wall_offset else 500
        contracts.append(
            OptionContract(
                underlying=underlying,
                expiry=date(2026, 6, 11),
                strike=Decimal(k),
                right=OptionRight.CALL,
                bid=Decimal("1.0"),
                ask=Decimal("1.1"),
                open_interest=coi,
                iv=iv,
                as_of=now,
            )
        )
        contracts.append(
            OptionContract(
                underlying=underlying,
                expiry=date(2026, 6, 11),
                strike=Decimal(k),
                right=OptionRight.PUT,
                bid=Decimal("1.0"),
                ask=Decimal("1.1"),
                open_interest=poi,
                iv=iv,
                as_of=now,
            )
        )
    return OptionChain(
        underlying=underlying, as_of=now, spot=Decimal(str(spot)), contracts=contracts
    )


@pytest.fixture
def ohlcv() -> OHLCV:
    return make_ohlcv()


@pytest.fixture
def htf_ohlcv() -> OHLCV:
    return make_ohlcv(n=120, timeframe=Timeframe.H1)


@pytest.fixture
def chain() -> OptionChain:
    return make_chain()
