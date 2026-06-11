"""CSV export for scanner results and signals — the proof layer, built in from day one."""

from __future__ import annotations

import csv
import io
import json

from ..schemas import ScannerResult, SignalPacket

SCANNER_COLUMNS = [
    "ts",
    "scanner_id",
    "symbol",
    "timeframe",
    "triggered",
    "direction",
    "score",
    "classification",
    "levels",
    "why",
    "why_now",
    "confidence",
    "evidence_for",
    "evidence_against",
    "invalidation",
]

SIGNAL_COLUMNS = [
    "created_at",
    "signal_id",
    "source_scanner",
    "symbol",
    "timeframe",
    "side",
    "state",
    "trade_style",
    "score",
    "classification",
    "entry",
    "stop",
    "targets",
    "rr",
    "regime",
    "why",
    "why_now",
    "invalidation",
]


def _ev_join(items) -> str:
    return "; ".join(f"{e.label}={e.value}({e.weight})" for e in items)


def scanner_results_to_csv(results: list[ScannerResult]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SCANNER_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in results:
        w.writerow(
            {
                "ts": r.ts.isoformat(),
                "scanner_id": r.scanner_id,
                "symbol": r.symbol,
                "timeframe": r.timeframe.value,
                "triggered": r.triggered,
                "direction": r.direction.value if r.direction else "",
                "score": round(r.score, 4),
                "classification": r.classification,
                "levels": json.dumps({k: str(v) for k, v in r.levels.items()}),
                "why": r.evidence.why,
                "why_now": r.evidence.why_now,
                "confidence": round(r.evidence.confidence, 4),
                "evidence_for": _ev_join(r.evidence.evidence_for),
                "evidence_against": _ev_join(r.evidence.evidence_against),
                "invalidation": r.evidence.invalidation.description,
            }
        )
    return buf.getvalue()


def signals_to_csv(signals: list[SignalPacket]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SIGNAL_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for s in signals:
        w.writerow(
            {
                "created_at": s.created_at.isoformat(),
                "signal_id": str(s.signal_id),
                "source_scanner": s.source_scanner,
                "symbol": s.symbol,
                "timeframe": s.timeframe.value,
                "side": s.side.value,
                "state": s.state.value,
                "trade_style": s.trade_style.value,
                "score": round(s.score, 4),
                "classification": s.classification,
                "entry": str(s.entry) if s.entry is not None else "",
                "stop": str(s.stop) if s.stop is not None else "",
                "targets": ",".join(str(t) for t in s.targets),
                "rr": s.rr if s.rr is not None else "",
                "regime": s.regime.value,
                "why": s.evidence.why,
                "why_now": s.evidence.why_now,
                "invalidation": s.evidence.invalidation.description,
            }
        )
    return buf.getvalue()
