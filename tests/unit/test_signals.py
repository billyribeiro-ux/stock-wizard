"""Signal builder, invalidation, and ensemble consensus."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.evidence import combine
from engine.features import FeatureFactory
from engine.scanners import ScanContext, build_scanner
from engine.schemas import Side, SignalState, Timeframe
from engine.signals import build_signal, is_invalidated

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _result(ohlcv, htf, sid="mtf_structure"):
    snap = FeatureFactory().build_snapshot(ohlcv)
    ctx = ScanContext(
        symbol="SPY", timeframe=Timeframe.M5, snapshot=snap, ohlcv=ohlcv, htf_ohlcv=htf, as_of=NOW
    )
    return build_scanner(sid).run(ctx), snap


def test_build_signal_has_trade_plan_when_triggered(ohlcv, htf_ohlcv):
    res, snap = _result(ohlcv, htf_ohlcv)
    sig = build_signal(res, snap)
    assert sig.symbol == "SPY"
    assert sig.state == SignalState.PROPOSED
    if res.triggered and res.direction in (Side.LONG, Side.SHORT):
        assert sig.entry is not None and sig.stop is not None
        assert len(sig.targets) >= 1
        assert sig.rr is not None and sig.rr > 0


def test_no_trade_signal_has_no_plan(ohlcv):
    from tests.conftest import make_ohlcv

    short = make_ohlcv(n=3)
    snap = FeatureFactory().build_snapshot(short)
    ctx = ScanContext(symbol="SPY", timeframe=Timeframe.M5, snapshot=snap, ohlcv=short, as_of=NOW)
    res = build_scanner("mtf_structure").run(ctx)
    sig = build_signal(res, snap)
    assert sig.entry is None
    assert sig.notes is not None


def test_invalidation_price_rules():
    from engine.schemas import InvalidationRule

    gt = InvalidationRule(description="", kind="price", level=100.0, comparator="gt")
    assert is_invalidated(gt, 101.0)
    assert not is_invalidated(gt, 99.0)

    lt = InvalidationRule(description="", kind="price", level=100.0, comparator="lt")
    assert is_invalidated(lt, 99.0)

    cross = InvalidationRule(description="", kind="options", level=100.0, comparator="crosses")
    assert is_invalidated(cross, 101.0, prev_price=99.0)
    assert not is_invalidated(cross, 101.0, prev_price=100.5)


def test_ensemble_consensus_agreement(ohlcv, htf_ohlcv):
    r1, _ = _result(ohlcv, htf_ohlcv, "mtf_structure")
    r2, _ = _result(ohlcv, htf_ohlcv, "volume_profile_poc")
    cons = combine([r1, r2])
    assert cons.action in {"trade", "scalp_only", "no_trade"}
    assert cons.direction in {Side.LONG, Side.SHORT, Side.NEUTRAL}


def test_ensemble_conflict_blocks():
    """Two equal-and-opposite triggered results -> no_trade."""
    from engine.schemas import EvidencePacket, InvalidationRule, ScannerResult

    def mk(direction):
        return ScannerResult(
            scanner_id="x",
            symbol="SPY",
            timeframe=Timeframe.M5,
            ts=NOW,
            triggered=True,
            direction=direction,
            score=0.8,
            classification="c",
            evidence=EvidencePacket(
                why="",
                why_now="",
                invalidation=InvalidationRule(description="", kind="price"),
                confidence=0.8,
            ),
        )

    cons = combine([mk(Side.LONG), mk(Side.SHORT)])
    assert cons.action == "no_trade"


def test_ensemble_edge_weights_break_ties():
    """Equal-and-opposite scores, but the LONG scanner has a higher validated edge -> LONG."""
    from engine.schemas import EvidencePacket, InvalidationRule, ScannerResult

    def mk(sid, direction):
        return ScannerResult(
            scanner_id=sid,
            symbol="SPY",
            timeframe=Timeframe.M5,
            ts=NOW,
            triggered=True,
            direction=direction,
            score=0.8,
            classification="c",
            evidence=EvidencePacket(
                why="",
                why_now="",
                invalidation=InvalidationRule(description="", kind="price"),
                confidence=0.8,
            ),
        )

    results = [mk("good", Side.LONG), mk("weak", Side.SHORT)]
    # good scanner carries 2x validated edge -> consensus leans LONG and trades
    cons = combine(results, edge_weights={"good": 2.0, "weak": 0.5})
    assert cons.direction == Side.LONG
    assert cons.long_weight > cons.short_weight
    assert cons.weights_used["good"] == 2.0


def test_edge_weight_from_calibrator():
    from engine.evidence import edge_weight_from_calibrator
    from engine.ml.calibration import ScoreCalibrator

    assert edge_weight_from_calibrator(None) == 1.0
    # a calibrator whose 0.7-score wins ~80% vs a 50% base -> weight > 1
    strong = ScoreCalibrator(x=[0.0, 1.0], y=[0.8, 0.8], base_rate=0.5, fitted=True).to_dict()
    assert edge_weight_from_calibrator(strong) > 1.0
    # a calibrator with win-rate below base -> weight < 1
    weak = ScoreCalibrator(x=[0.0, 1.0], y=[0.4, 0.4], base_rate=0.5, fitted=True).to_dict()
    assert edge_weight_from_calibrator(weak) < 1.0
