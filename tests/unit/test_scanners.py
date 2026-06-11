"""Each scanner emits a valid ScannerResult with an EvidencePacket."""

from __future__ import annotations

from datetime import UTC, date, datetime

from engine.features import FeatureFactory
from engine.scanners import ScanContext, build_scanner, list_scanner_ids, list_specs
from engine.schemas import CongressTrade, InsiderTransaction, ScannerResult, Side, Timeframe

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _ctx(ohlcv, htf, chain=None, insider=None, congress=None):
    snap = FeatureFactory().build_snapshot(ohlcv, chain=chain)
    return ScanContext(
        symbol="SPY",
        timeframe=Timeframe.M5,
        snapshot=snap,
        ohlcv=ohlcv,
        htf_ohlcv=htf,
        chain=chain,
        insider=insider or [],
        congress=congress or [],
        as_of=NOW,
    )


def test_registry_lists_all():
    ids = list_scanner_ids()
    assert {
        "mtf_structure",
        "volume_profile_poc",
        "spx_gamma_command",
        "insider_congress_flow",
    } <= set(ids)
    for spec in list_specs():
        assert spec.scanner_id and spec.name and spec.params_schema


def test_mtf_structure_triggers_with_trend(ohlcv, htf_ohlcv):
    res = build_scanner("mtf_structure").run(_ctx(ohlcv, htf_ohlcv))
    assert isinstance(res, ScannerResult)
    assert 0.0 <= res.score <= 1.0
    assert res.evidence.why and res.evidence.invalidation.kind


def test_volume_profile_returns_classification(ohlcv, htf_ohlcv):
    res = build_scanner("volume_profile_poc").run(_ctx(ohlcv, htf_ohlcv))
    assert res.classification in {
        "acceptance_above_value",
        "vah_rejection",
        "breakdown_below_value",
        "val_reclaim_watch",
        "poc_balance",
        "inside_value",
        "insufficient_data",
    }
    assert "poc" in res.levels or res.classification == "insufficient_data"


def test_spx_gamma_command_classifies(ohlcv, htf_ohlcv, chain):
    res = build_scanner("spx_gamma_command").run(_ctx(ohlcv, htf_ohlcv, chain=chain))
    assert res.scanner_id == "spx_gamma_command"
    assert res.classification in {
        "scalp_long",
        "scalp_short",
        "reversal_long",
        "reversal_short",
        "top",
        "bottom",
        "gamma_squeeze",
        "no_trade",
        "insufficient_data",
    }
    if res.triggered:
        assert res.direction in {Side.LONG, Side.SHORT}
        assert "spot" in res.levels


def test_insider_congress_flow_bullish(ohlcv, htf_ohlcv):
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
    res = build_scanner("insider_congress_flow").run(
        _ctx(ohlcv, htf_ohlcv, insider=insider, congress=congress)
    )
    assert res.triggered
    assert res.direction == Side.LONG
    assert res.classification == "insider_accumulation"


def test_scanner_handles_insufficient_data():
    from tests.conftest import make_ohlcv

    short = make_ohlcv(n=3)
    res = build_scanner("mtf_structure").run(_ctx(short, None))
    assert res.triggered is False
    assert res.classification == "insufficient_data"
