"""arq job enqueue helpers. The worker consumes these; the API falls back to running
inline (FastAPI background task) when Redis/arq is unavailable, so the slice works
without a separate worker process."""

from __future__ import annotations

from arq import create_pool
from arq.connections import RedisSettings

from common.settings import get_settings

_settings = get_settings()


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(_settings.redis_url)


async def enqueue_scan(run_id: str) -> bool:
    """Enqueue a scan job. Returns True if enqueued, False if Redis is unavailable."""
    try:
        pool = await create_pool(_redis_settings())
        await pool.enqueue_job("run_scan", run_id)
        await pool.aclose()
        return True
    except Exception:
        return False
