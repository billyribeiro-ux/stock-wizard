"""Scanner catalog endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from engine.scanners import list_specs

from ..security import require_token

router = APIRouter(tags=["scanners"], dependencies=[Depends(require_token)])


@router.get("/scanners")
async def get_scanners() -> list[dict]:
    return [s.model_dump(mode="json") for s in list_specs()]
