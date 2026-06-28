"""End-to-end pipeline against a real Postgres + Redis and the real FastAPI app.

Exercises the full chain through the actual HTTP API and DB: health -> add an encrypted
vendor key -> create a scan -> execute it (the worker's code path) -> read results + signals
(carrying the regime/edge fields) -> run a forward backtest -> confirm the out-of-sample edge
weight is persisted and served. The market-data vendor is stubbed with deterministic
synthetic bars so the test is hermetic (no live network).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from engine.schemas import OHLCV, MarketBar, Timeframe

AUTH = {"Authorization": "Bearer test-token"}


def _synth_ohlcv(symbol: str, timeframe: Timeframe, start, end=None) -> OHLCV:
    """~600 trending daily bars — enough for volume profile + a forward-test split."""
    bars: list[MarketBar] = []
    base = datetime(2022, 1, 3, tzinfo=UTC)
    px = 100.0
    for i in range(600):
        px = 100.0 + 0.10 * i + 4.0 * math.sin(i / 9.0)
        bars.append(
            MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                ts=base + timedelta(days=i),
                open=Decimal(str(round(px - 0.3, 2))),
                high=Decimal(str(round(px + 1.2, 2))),
                low=Decimal(str(round(px - 1.2, 2))),
                close=Decimal(str(round(px, 2))),
                volume=1_000_000 + (i % 7) * 50_000,
                source="fmp",
            )
        )
    return OHLCV(symbol=symbol, timeframe=timeframe, source="fmp", bars=bars)


class _FakeFMP:
    name = "fmp"

    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        self.api_key = api_key

    def get_ohlcv(self, symbol, timeframe, start, end=None):
        return _synth_ohlcv(symbol, timeframe, start, end)


@pytest.fixture(autouse=True)
def _stub_fmp(monkeypatch):
    # registry.build_ohlcv_source does `from .fmp_source import FMPSource` at call time,
    # so patching the attribute reroutes both the scan and backtest data resolvers.
    monkeypatch.setattr("engine.data.fmp_source.FMPSource", _FakeFMP)


@pytest.fixture
async def client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_reports_db_and_redis(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["redis"] is True


async def test_full_pipeline(client):
    from app.db import SessionLocal
    from app.services.backtest_service import execute_backtest
    from app.services.scan_service import execute_scan

    # 1) add an encrypted FMP key; it must come back masked, never in plaintext.
    r = await client.post(
        "/vendors/keys",
        headers=AUTH,
        json={"vendor": "fmp", "label": "e2e", "api_key": "fmp_secret_ABCD1234", "scopes": []},
    )
    assert r.status_code == 201
    listed = (await client.get("/vendors", headers=AUTH)).json()
    fmp_rows = [v for v in listed if v["vendor"] == "fmp"]
    assert fmp_rows and fmp_rows[-1]["masked_key"].endswith("1234")
    assert all("fmp_secret" not in str(v) for v in listed)  # plaintext never leaks

    # 2) create a scan over the synthetic feed.
    r = await client.post(
        "/scans",
        headers=AUTH,
        json={
            "scanner_id": "volume_profile_poc",
            "symbols": ["SPY"],
            "timeframe": "1d",
            "history": "2y",
        },
    )
    assert r.status_code == 202
    run_id = r.json()["run_id"]

    # 3) execute it via the worker's code path (deterministic), then read back over HTTP.
    async with SessionLocal() as session:
        triggered = await execute_scan(session, run_id)
    assert triggered >= 0  # ran without error

    scan = (await client.get(f"/scans/{run_id}", headers=AUTH)).json()
    assert scan["status"] == "done"
    results = (await client.get(f"/scans/{run_id}/results", headers=AUTH)).json()
    assert results["total"] >= 1

    signals = (await client.get("/signals", headers=AUTH)).json()
    assert signals["items"], "expected at least one signal"
    sig = signals["items"][0]
    # the regime/edge plumbing reaches the persisted signal
    assert "regime_aligned" in sig and "edge_weight" in sig
    assert sig["source_scanner"] == "volume_profile_poc"

    # 4) forward backtest -> persists an out-of-sample edge weight.
    r = await client.post(
        "/backtests",
        headers=AUTH,
        json={
            "scanner_id": "volume_profile_poc",
            "symbol": "SPY",
            "timeframe": "1d",
            "history": "5y",
            "params": {"mode": "forward"},
        },
    )
    assert r.status_code == 202
    bt_id = r.json()["backtest_id"]
    async with SessionLocal() as session:
        await execute_backtest(session, bt_id)

    bt = (await client.get(f"/backtests/{bt_id}", headers=AUTH)).json()
    assert bt["status"] == "done"
    assert bt["result"]["mode"] == "forward"
    assert bt["result"]["promotion"] in {"promote", "keep_testing", "retire"}

    # 5) the edge weight is now served and applied live.
    weights = (await client.get("/backtests/edge-weights", headers=AUTH)).json()["items"]
    vp = [w for w in weights if w["scanner_id"] == "volume_profile_poc"]
    assert vp, "forward test should have persisted an edge weight"
    assert vp[0]["edge_weight"] is not None


async def test_auth_required(client):
    assert (await client.get("/vendors")).status_code == 401
    assert (
        await client.get("/vendors", headers={"Authorization": "Bearer wrong"})
    ).status_code == 403
