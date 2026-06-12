"""Health + data-health endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..db import SessionLocal, engine
from ..pubsub import get_redis
from ..repositories import repo

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    db_ok = redis_ok = timescale = False
    health_rows: list[dict] = []
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
            res = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
            )
            timescale = res.first() is not None
        async with SessionLocal() as session:
            health_rows = await repo.data_health(session)
    except Exception:
        db_ok = db_ok and False
    try:
        r = get_redis()
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status,
        "db": db_ok,
        "redis": redis_ok,
        "timescale": timescale,
        "data_health": health_rows,
    }
