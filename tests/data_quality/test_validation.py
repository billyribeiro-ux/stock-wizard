"""Data-quality validation: flags and drops bad bars."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from engine.data import validate
from engine.schemas import OHLCV, BarFlag, MarketBar, Timeframe

BASE = datetime(2026, 6, 10, 14, 0, tzinfo=UTC)


def _bar(i, close, vol=100000, high=None, low=None):
    c = Decimal(str(close))
    return MarketBar(
        symbol="X",
        timeframe=Timeframe.M5,
        ts=BASE + timedelta(minutes=5 * i),
        open=c,
        high=Decimal(str(high)) if high else c + 1,
        low=Decimal(str(low)) if low else c - 1,
        close=c,
        volume=vol,
    )


def test_zero_volume_flagged():
    ohlcv = OHLCV(symbol="X", timeframe=Timeframe.M5, bars=[_bar(0, 100), _bar(1, 100, vol=0)])
    cleaned, _ = validate(ohlcv)
    assert BarFlag.ZERO_VOLUME in cleaned.bars[1].quality_flags


def test_split_suspect_flagged_on_large_jump():
    ohlcv = OHLCV(symbol="X", timeframe=Timeframe.M5, bars=[_bar(0, 100), _bar(1, 50)])
    cleaned, issues = validate(ohlcv)
    assert BarFlag.SPLIT_SUSPECT in cleaned.bars[1].quality_flags
    assert any(i.issue == "split_suspect" for i in issues)


def test_out_of_hours_flagged():
    # 3:00 UTC is well outside US RTH.
    ts = datetime(2026, 6, 10, 3, 0, tzinfo=UTC)
    bar = MarketBar(
        symbol="X",
        timeframe=Timeframe.M5,
        ts=ts,
        open=Decimal(100),
        high=Decimal(101),
        low=Decimal(99),
        close=Decimal(100),
        volume=1000,
    )
    cleaned, _ = validate(OHLCV(symbol="X", timeframe=Timeframe.M5, bars=[bar]))
    assert BarFlag.OUT_OF_HOURS in cleaned.bars[0].quality_flags


def test_valid_series_passes_clean():
    bars = [_bar(i, 100 + i * 0.1) for i in range(10)]
    cleaned, issues = validate(OHLCV(symbol="X", timeframe=Timeframe.M5, bars=bars))
    assert len(cleaned.bars) == 10
    assert not any(i.issue == "impossible" for i in issues)
