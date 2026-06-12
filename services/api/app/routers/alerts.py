"""Alert rule CRUD + event history (buy/sell signal alerts)."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from engine.schemas import AlertRule, Side

from ..db import get_session
from ..repositories import repo
from ..security import require_token

router = APIRouter(tags=["alerts"], dependencies=[Depends(require_token)])


class CreateAlertRule(BaseModel):
    name: str
    scanner_ids: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    sides: list[Side] = Field(default_factory=list)
    classifications: list[str] = Field(default_factory=list)
    min_score: float = 0.6
    channel: str = "log"
    target: str = ""
    cooldown_seconds: int = 0


class EnableBody(BaseModel):
    enabled: bool


@router.get("/alerts/rules")
async def list_rules(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await repo.list_alert_rules(session)
    return {"items": [r.config for r in rows]}


@router.post("/alerts/rules", status_code=201)
async def create_rule(req: CreateAlertRule, session: AsyncSession = Depends(get_session)) -> dict:
    rule = AlertRule(
        id=uuid4(),
        name=req.name,
        scanner_ids=req.scanner_ids,
        symbols=req.symbols,
        sides=req.sides,
        classifications=req.classifications,
        min_score=req.min_score,
        channel=req.channel,
        target=req.target,
        cooldown_seconds=req.cooldown_seconds,
    )
    await repo.add_alert_rule(
        session, rule.id, rule.name, rule.enabled, rule.channel, rule.model_dump(mode="json")
    )
    return {"id": str(rule.id)}


@router.patch("/alerts/rules/{rule_id}")
async def set_enabled(
    rule_id: UUID, body: EnableBody, session: AsyncSession = Depends(get_session)
) -> dict:
    row = await repo.set_alert_rule_enabled(session, rule_id, body.enabled)
    if row is None:
        raise HTTPException(404, "rule not found")
    return {"id": str(rule_id), "enabled": body.enabled}


@router.delete("/alerts/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    if not await repo.delete_alert_rule(session, rule_id):
        raise HTTPException(404, "rule not found")


@router.get("/alerts/events")
async def list_events(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await repo.list_alert_events(session)
    return {
        "items": [
            {
                "id": str(r.id),
                "rule_id": str(r.rule_id),
                "signal_id": str(r.signal_id),
                "symbol": r.symbol,
                "side": r.side,
                "scanner_id": r.scanner_id,
                "classification": r.classification,
                "score": r.score,
                "channel": r.channel,
                "delivered": r.delivered,
                "error": r.error,
                "message": r.message,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
