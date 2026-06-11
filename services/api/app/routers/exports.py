"""CSV / PDF export endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from engine.reports import render_evidence_pdf, scanner_results_to_csv
from engine.schemas import ScannerResult

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
