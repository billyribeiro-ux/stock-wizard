"""CSV and HTML/PDF export."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.features import FeatureFactory
from engine.reports import render_evidence_html, scanner_results_to_csv, signals_to_csv
from engine.scanners import ScanContext, build_scanner
from engine.schemas import Timeframe
from engine.signals import build_signal

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _results(ohlcv, htf):
    snap = FeatureFactory().build_snapshot(ohlcv)
    out = []
    for sid in ("mtf_structure", "volume_profile_poc"):
        ctx = ScanContext(
            symbol="SPY",
            timeframe=Timeframe.M5,
            snapshot=snap,
            ohlcv=ohlcv,
            htf_ohlcv=htf,
            as_of=NOW,
        )
        out.append((build_scanner(sid).run(ctx), snap))
    return out


def test_scanner_csv_has_header_and_rows(ohlcv, htf_ohlcv):
    results = [r for r, _ in _results(ohlcv, htf_ohlcv)]
    csv = scanner_results_to_csv(results)
    lines = csv.strip().splitlines()
    assert lines[0].startswith("ts,scanner_id,symbol")
    assert len(lines) == len(results) + 1
    assert "why" in lines[0]


def test_signal_csv(ohlcv, htf_ohlcv):
    sigs = [build_signal(r, s) for r, s in _results(ohlcv, htf_ohlcv)]
    csv = signals_to_csv(sigs)
    assert "signal_id" in csv.splitlines()[0]


def test_evidence_html_renders(ohlcv, htf_ohlcv):
    results = [r for r, _ in _results(ohlcv, htf_ohlcv)]
    html = render_evidence_html(results)
    assert "<html" in html.lower()
    assert "Evidence for" in html
    assert "Invalidation" in html


def test_evidence_pdf_renders(ohlcv, htf_ohlcv):
    """WeasyPrint native libs are present in CI/dev; produce a real PDF."""
    from engine.reports import render_evidence_pdf

    results = [r for r, _ in _results(ohlcv, htf_ohlcv)]
    pdf = render_evidence_pdf(results)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000
