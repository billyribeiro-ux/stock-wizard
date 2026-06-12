"""CSV / PDF export endpoints."""

from __future__ import annotations

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from engine.reports import render_backtest_pdf, render_evidence_pdf, scanner_results_to_csv
from engine.schemas import BacktestResult, ScannerResult

from ..db import get_session
from ..repositories import repo
from ..security import require_token

router = APIRouter(tags=["exports"], dependencies=[Depends(require_token)])


@router.get("/exports/scan/{run_id}")
async def export_scan(
    run_id: UUID,
    fmt: str = Query("csv", pattern="^(csv|pdf)$"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    payloads = await repo.list_results(session, run_id)
    if not payloads:
        raise HTTPException(404, "no results for run")
    results = [ScannerResult.model_validate(p) for p in payloads]

    if fmt == "csv":
        body = scanner_results_to_csv(results)
        return Response(
            content=body,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="scan_{run_id}.csv"'},
        )
    try:
        pdf = render_evidence_pdf(results, title=f"Scan {run_id}")
    except Exception as exc:
        raise HTTPException(500, f"PDF rendering unavailable: {exc}") from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="scan_{run_id}.pdf"'},
    )


@router.get("/exports/backtest/{backtest_id}")
async def export_backtest(
    backtest_id: UUID,
    fmt: str = Query("pdf", pattern="^(csv|pdf)$"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    bt = await repo.get_backtest(session, backtest_id)
    if bt is None or not bt.payload:
        raise HTTPException(404, "backtest not found or not finished")
    result = BacktestResult.model_validate(bt.payload)

    if fmt == "csv":
        buf = io.StringIO()
        cols = [
            "entry_ts",
            "side",
            "entry_price",
            "exit_ts",
            "exit_price",
            "pnl",
            "return_pct",
            "mfe",
            "mae",
            "exit_reason",
        ]
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for t in result.trades:
            row = t.model_dump(mode="json")
            w.writerow({c: row.get(c, "") for c in cols})
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="backtest_{backtest_id}.csv"'},
        )
    try:
        pdf = render_backtest_pdf(result, title=f"Backtest {bt.scanner_id}")
    except Exception as exc:
        raise HTTPException(500, f"PDF rendering unavailable: {exc}") from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="backtest_{backtest_id}.pdf"'},
    )
