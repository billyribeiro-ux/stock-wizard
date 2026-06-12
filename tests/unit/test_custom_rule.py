"""User Rule Builder scanner."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.features import FeatureFactory
from engine.scanners import ScanContext, build_scanner
from engine.schemas import Side, Timeframe
from tests.conftest import make_ohlcv

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _ctx(params):
    ohlcv = make_ohlcv(n=200)
    snap = FeatureFactory().build_snapshot(ohlcv)
    return ScanContext(
        symbol="SPY", timeframe=Timeframe.M5, snapshot=snap, ohlcv=ohlcv, as_of=NOW, params=params
    )


def test_always_true_rule_triggers():
    params = {
        "direction": "LONG",
        "name": "trivial",
        "conditions": [{"feature": "rvol", "op": "gt", "threshold": -1}],
    }
    res = build_scanner("custom_rule", params).run(_ctx(params))
    assert res.triggered and res.direction == Side.LONG
    assert res.classification == "rule_hit"
    assert res.evidence.evidence_for


def test_impossible_rule_misses():
    params = {
        "direction": "SHORT",
        "conditions": [{"feature": "rvol", "op": "gt", "threshold": 1e9}],
    }
    res = build_scanner("custom_rule", params).run(_ctx(params))
    assert not res.triggered
    assert res.classification == "rule_miss"
    assert res.evidence.evidence_against


def test_no_conditions_is_flat():
    params = {"direction": "LONG", "conditions": []}
    res = build_scanner("custom_rule", params).run(_ctx(params))
    assert not res.triggered and res.classification == "no_conditions"


def test_invalid_feature_blocks():
    params = {
        "direction": "LONG",
        "conditions": [{"feature": "not_a_feature", "op": "gt", "threshold": 0}],
    }
    res = build_scanner("custom_rule", params).run(_ctx(params))
    assert not res.triggered
