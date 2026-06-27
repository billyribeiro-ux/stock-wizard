"""Contract layer: invariants, round-trips, JSON-schema export."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from engine.schemas import (
    AssetClass,
    EvidenceItem,
    EvidencePacket,
    InvalidationRule,
    MarketBar,
    ScannerResult,
    Side,
    SignalPacket,
    Timeframe,
)
from engine.schemas.export_jsonschema import build_schema

NOW = datetime(2026, 6, 11, 14, 30, tzinfo=UTC)


def _evidence() -> EvidencePacket:
    return EvidencePacket(
        why="thesis",
        why_now="trigger",
        evidence_for=[
            EvidenceItem(kind="options", label="x", value=1.0, weight=0.5, direction=Side.LONG)
        ],
        invalidation=InvalidationRule(description="d", kind="price", level=1.0, comparator="lt"),
        confidence=0.6,
    )


def test_marketbar_rejects_naive_datetime():
    with pytest.raises(ValidationError):
        MarketBar(
            symbol="X",
            timeframe=Timeframe.M5,
            ts=datetime(2026, 1, 1),
            open=Decimal(1),
            high=Decimal(1),
            low=Decimal(1),
            close=Decimal(1),
            volume=0,
        )


def test_marketbar_rejects_bad_ohlc():
    with pytest.raises(ValidationError):
        MarketBar(
            symbol="X",
            timeframe=Timeframe.M5,
            ts=NOW,
            open=Decimal(5),
            high=Decimal(1),
            low=Decimal(2),
            close=Decimal(3),
            volume=0,
        )


def test_timeframe_seconds_and_intraday():
    assert Timeframe.M5.seconds == 300
    assert Timeframe.M5.is_intraday
    assert not Timeframe.D1.is_intraday


def test_signal_packet_round_trip():
    sig = SignalPacket(
        source_scanner="spx_gamma_command",
        symbol="SPY",
        asset_class=AssetClass.ETF,
        timeframe=Timeframe.M5,
        as_of=NOW,
        side=Side.SHORT,
        score=0.7,
        evidence=_evidence(),
        entry=Decimal("504.9"),
        stop=Decimal("505.5"),
        targets=[Decimal("502")],
    )
    again = SignalPacket.model_validate_json(sig.model_dump_json())
    assert again.signal_id == sig.signal_id
    assert again.evidence.why == "thesis"
    assert again.side is Side.SHORT


def test_scanner_result_extra_forbidden():
    with pytest.raises(ValidationError):
        ScannerResult(  # type: ignore[call-arg]  # intentional: extra field must be rejected
            scanner_id="s",
            symbol="SPY",
            timeframe=Timeframe.M5,
            ts=NOW,
            triggered=False,
            score=0.0,
            classification="x",
            evidence=_evidence(),
            bogus_field=1,
        )


def test_evidence_net_weight():
    ev = _evidence()
    assert ev.net_evidence_weight == pytest.approx(0.5)


def test_jsonschema_export_has_core_models():
    schema = build_schema()
    for name in ("SignalPacket", "ScannerResult", "OHLCV", "OptionChain", "ReportSpec"):
        assert name in schema["$defs"]
