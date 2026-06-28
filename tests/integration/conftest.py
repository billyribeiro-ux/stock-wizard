"""Integration-test environment.

Points the app at a real local Postgres + Redis and sets the auth/crypto secrets *before*
the app or settings are imported (settings are lru-cached and the engine is built at import
time). Skips the whole integration suite cleanly if the database/redis aren't reachable, so
unit-only environments stay green.
"""

from __future__ import annotations

import os

import pytest

_PG = "postgresql+asyncpg://wizard:wizard@localhost:5432/stockwizard"
_PG_SYNC = "postgresql+psycopg://wizard:wizard@localhost:5432/stockwizard"

os.environ.setdefault("DATABASE_URL", _PG)
os.environ.setdefault("DATABASE_URL_SYNC", _PG_SYNC)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("INTERNAL_API_TOKEN", "test-token")
# A deterministic Fernet key so SecretBox can encrypt vendor keys in tests.
os.environ.setdefault("MASTER_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")


@pytest.fixture(autouse=True)
async def _dispose_engine():
    """Drain the global async engine's pool inside each test's event loop, so asyncpg
    connections close before pytest-asyncio tears the loop down (avoids 'Event loop is
    closed' noise from the shared module-level engine)."""
    yield
    from app.db import engine

    await engine.dispose()


def _infra_reachable() -> bool:
    import socket

    for host, port in (("localhost", 5432), ("localhost", 6379)):
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            return False
    return True


pytestmark = pytest.mark.skipif(not _infra_reachable(), reason="local Postgres/Redis not reachable")
