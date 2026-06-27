"""Alert rule matching + dispatch."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.alerts import dispatch, matches, render_message
from engine.schemas import (
    AlertChannel,
    AlertRule,
    AssetClass,
    EvidencePacket,
    InvalidationRule,
    Side,
    SignalPacket,
    Timeframe,
)

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _signal(scanner="spx_gamma_command", side=Side.LONG, score=0.8, symbol="SPY", cls="scalp_long"):
    ev = EvidencePacket(
        why="w",
        why_now="trigger now",
        invalidation=InvalidationRule(description="x", kind="price"),
        confidence=score,
    )
    return SignalPacket(
        source_scanner=scanner,
        symbol=symbol,
        asset_class=AssetClass.ETF,
        timeframe=Timeframe.M5,
        as_of=NOW,
        side=side,
        score=score,
        classification=cls,
        evidence=ev,
    )


def test_matches_score_gate():
    rule = AlertRule(name="hi-conf", min_score=0.7)
    assert matches(rule, _signal(score=0.8))
    assert not matches(rule, _signal(score=0.5))


def test_matches_filters():
    rule = AlertRule(
        name="spy gamma longs",
        scanner_ids=["spx_gamma_command"],
        symbols=["SPY"],
        sides=[Side.LONG],
        min_score=0.5,
    )
    assert matches(rule, _signal())
    assert not matches(rule, _signal(side=Side.SHORT))
    assert not matches(rule, _signal(symbol="QQQ"))
    assert not matches(rule, _signal(scanner="mtf_structure"))


def test_disabled_rule_never_matches():
    rule = AlertRule(name="off", enabled=False, min_score=0.0)
    assert not matches(rule, _signal())


def test_render_message_contains_key_facts():
    msg = render_message(AlertRule(name="R"), _signal())
    assert "LONG" in msg and "SPY" in msg and "spx_gamma_command" in msg


def test_dispatch_log_channel_succeeds():
    ok, err = dispatch(AlertRule(name="R", channel=AlertChannel.LOG), _signal(), "m")
    assert ok and err is None


def test_dispatch_webhook_without_target_fails():
    ok, err = dispatch(AlertRule(name="R", channel=AlertChannel.WEBHOOK), _signal(), "m")
    assert not ok and "webhook" in (err or "")


def test_dispatch_email_stub():
    ok, err = dispatch(AlertRule(name="R", channel=AlertChannel.EMAIL), _signal(), "m")
    assert not ok and "email" in (err or "")
