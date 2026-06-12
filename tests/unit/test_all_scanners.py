"""Every registered scanner runs and returns a valid ScannerResult + EvidencePacket."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from engine.features import FeatureFactory
from engine.scanners import ScanContext, build_scanner, list_scanner_ids
from engine.schemas import CongressTrade, InsiderTransaction, ScannerResult, Side, Timeframe

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _full_ctx(ohlcv, htf, chain):
    snap = FeatureFactory().build_snapshot(ohlcv, chain=chain)
    insider = [
        InsiderTransaction(
            symbol="SPY",
            insider_name="CEO",
            transaction_date=date(2026, 6, 1),
            side=Side.LONG,
            shares=10000,
            source="edgar",
        ),
        InsiderTransaction(
            symbol="SPY",
            insider_name="CFO",
            transaction_date=date(2026, 6, 3),
            side=Side.LONG,
            shares=5000,
            source="edgar",
        ),
    ]
    congress = [
        CongressTrade(
            symbol="SPY",
            representative="Rep X",
            transaction_date=date(2026, 6, 2),
            side=Side.LONG,
            source="finnhub",
        )
    ]
    return ScanContext(
        symbol="SPY",
        timeframe=Timeframe.M5,
        snapshot=snap,
        ohlcv=ohlcv,
        htf_ohlcv=htf,
        chain=chain,
        insider=insider,
        congress=congress,
        as_of=NOW,
    )


@pytest.mark.parametrize("scanner_id", list_scanner_ids())
def test_scanner_returns_valid_result(scanner_id, ohlcv, htf_ohlcv, chain):
    ctx = _full_ctx(ohlcv, htf_ohlcv, chain)
    res = build_scanner(scanner_id).run(ctx)
    assert isinstance(res, ScannerResult)
    assert res.scanner_id == scanner_id
    assert 0.0 <= res.score <= 1.0
    assert res.classification
    assert res.evidence is not None and res.evidence.invalidation is not None
    if res.triggered:
        assert res.direction in {Side.LONG, Side.SHORT, Side.NEUTRAL, None}


def test_catalog_size():
    # Foundation 4 + Wave B additions.
    assert len(list_scanner_ids()) >= 30


@pytest.mark.parametrize("scanner_id", list_scanner_ids())
def test_scanner_handles_empty_gracefully(scanner_id, chain):
    """Scanners must not crash on a tiny/empty bar window."""
    from tests.conftest import make_ohlcv

    tiny = make_ohlcv(n=3)
    snap = FeatureFactory().build_snapshot(tiny, chain=chain)
    ctx = ScanContext(
        symbol="SPY", timeframe=Timeframe.M5, snapshot=snap, ohlcv=tiny, chain=chain, as_of=NOW
    )
    res = build_scanner(scanner_id).run(ctx)
    assert isinstance(res, ScannerResult)
