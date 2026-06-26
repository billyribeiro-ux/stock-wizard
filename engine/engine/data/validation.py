"""Data validation — annotate bars with quality flags and drop impossible ones.

Catches the blueprint's "bad bars, gaps, splits, timezones, impossible values" so a
scanner never silently trusts garbage. Returns a cleaned OHLCV plus a list of issues.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from common.timeutils import is_regular_hours

from ..schemas import OHLCV, BarFlag, MarketBar


@dataclass
class ValidationIssue:
    ts: str
    issue: str
    detail: str


def validate(ohlcv: OHLCV, drop_impossible: bool = True) -> tuple[OHLCV, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    cleaned: list[MarketBar] = []
    prev: MarketBar | None = None
    gap_factor = Decimal("0.35")  # >35% bar-to-bar jump on intraday => split/gap suspect

    for bar in ohlcv.bars:
        flags = list(bar.quality_flags)

        if bar.high < bar.low or bar.open <= 0 or bar.close <= 0:
            issues.append(ValidationIssue(bar.ts.isoformat(), "impossible", "bad OHLC"))
            if drop_impossible:
                continue
            flags.append(BarFlag.IMPOSSIBLE)

        if bar.volume == 0:
            flags.append(BarFlag.ZERO_VOLUME)

        if ohlcv.timeframe.is_intraday and not is_regular_hours(bar.ts):
            flags.append(BarFlag.OUT_OF_HOURS)

        if prev is not None:
            if bar.ts <= prev.ts:
                issues.append(ValidationIssue(bar.ts.isoformat(), "duplicate", "non-increasing ts"))
                continue
            if prev.close > 0:
                jump = abs(bar.close - prev.close) / prev.close
                if jump > gap_factor:
                    flags.append(BarFlag.SPLIT_SUSPECT)
                    issues.append(
                        ValidationIssue(bar.ts.isoformat(), "split_suspect", f"{jump:.1%} jump")
                    )
            gap_bars = (bar.ts - prev.ts).total_seconds() / ohlcv.timeframe.seconds
            if ohlcv.timeframe.is_intraday and is_regular_hours(bar.ts) and gap_bars > 3:
                flags.append(BarFlag.GAP)

        cleaned.append(bar.model_copy(update={"quality_flags": list(dict.fromkeys(flags))}))
        prev = bar

    return (
        OHLCV(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            asset_class=ohlcv.asset_class,
            source=ohlcv.source,
            bars=cleaned,
        ),
        issues,
    )
