"""Evaluate a signal against enabled alert rules and dispatch + record matches."""

from __future__ import annotations

from engine.alerts import dispatch, matches, render_message
from engine.schemas import AlertEvent, AlertRule, SignalPacket

from ..repositories import repo


async def evaluate_alerts(session, signal: SignalPacket) -> list[AlertEvent]:
    rows = await repo.list_alert_rules(session, enabled_only=True)
    events: list[AlertEvent] = []
    for row in rows:
        try:
            rule = AlertRule.model_validate(row.config)
        except Exception:
            continue
        if not matches(rule, signal):
            continue
        message = render_message(rule, signal)
        delivered, error = dispatch(rule, signal, message)
        event = AlertEvent(
            rule_id=rule.id,
            rule_name=rule.name,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=signal.side,
            scanner_id=signal.source_scanner,
            classification=signal.classification,
            score=signal.score,
            channel=rule.channel,
            delivered=delivered,
            error=error,
            message=message,
        )
        await repo.add_alert_event(session, event)
        events.append(event)
    return events
