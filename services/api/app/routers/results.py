"""Single-result + signals + live stream endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..pubsub import subscribe_signals
from ..repositories import repo
from ..security import require_token

router = APIRouter(tags=["results"], dependencies=[Depends(require_token)])


@router.get("/results/{result_id}")
async def get_result(result_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    payload = await repo.get_result(session, result_id)
    if payload is None:
        raise HTTPException(404, "result not found")
    return payload


@router.get("/signals")
async def get_signals(
    run_id: UUID | None = None, limit: int = 100, session: AsyncSession = Depends(get_session)
) -> dict:
    items = await repo.list_signals(session, run_id=run_id, limit=limit)
    return {"items": items}


@router.get("/stream/signals")
async def stream_signals(run_id: UUID, request: Request) -> StreamingResponse:
    """Server-Sent Events bridging the Redis signal channel for this run."""

    async def event_gen():
        async for payload in subscribe_signals(str(run_id)):
            if await request.is_disconnected():
                break
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
