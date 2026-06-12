"""Match signals against alert rules and dispatch to channels.

Channels: ``log`` (always succeeds, for the in-app feed), ``webhook`` (HTTP POST the
signal JSON), ``email`` (stub — wire an SMTP/provider adapter later). Matching is pure
and unit-tested; dispatch is best-effort and returns (delivered, error).
"""

from __future__ import annotations

import json

from ..schemas import AlertChannel, AlertRule, SignalPacket


def matches(rule: AlertRule, signal: SignalPacket) -> bool:
    if not rule.enabled:
        return False
    if signal.score < rule.min_score:
        return False
    if rule.scanner_ids and signal.source_scanner not in rule.scanner_ids:
        return False
    if rule.symbols and signal.symbol.upper() not in {s.upper() for s in rule.symbols}:
        return False
    if rule.sides and signal.side not in rule.sides:
        return False
    return not (rule.classifications and signal.classification not in rule.classifications)


def render_message(rule: AlertRule, signal: SignalPacket) -> str:
    entry = f" @ {signal.entry}" if signal.entry is not None else ""
    stop = f" stop {signal.stop}" if signal.stop is not None else ""
    tgt = f" target {signal.targets[0]}" if signal.targets else ""
    return (
        f"[{rule.name}] {signal.side.value} {signal.symbol} "
        f"({signal.source_scanner}: {signal.classification}, score {signal.score:.2f})"
        f"{entry}{stop}{tgt} — {signal.evidence.why_now}"
    )


def dispatch(
    rule: AlertRule, signal: SignalPacket, message: str, timeout: float = 8.0
) -> tuple[bool, str | None]:
    """Deliver an alert. Returns (delivered, error)."""
    if rule.channel == AlertChannel.LOG:
        return True, None
    if rule.channel == AlertChannel.WEBHOOK:
        if not rule.target:
            return False, "no webhook URL configured"
        import requests

        payload = {"message": message, "signal": signal.model_dump(mode="json")}
        try:
            resp = requests.post(
                rule.target,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            if resp.status_code >= 400:
                return False, f"webhook HTTP {resp.status_code}"
            return True, None
        except Exception as exc:
            return False, str(exc)
    if rule.channel == AlertChannel.EMAIL:
        # Stub: wire an SMTP / provider adapter (configurable in Settings) later.
        return False, "email channel not configured"
    return False, f"unknown channel '{rule.channel}'"
