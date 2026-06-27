"""Charles Schwab adapter — OAuth bundle codec, authorize URL, chain parsing, wiring.

All offline: no live OAuth/network. We exercise the credential JSON round-trip, the
authorize-URL builder, leg parsing (real vendor greeks + the -999.0 sentinel), the
chain/pricehistory parsing via a stubbed ``_get``, and the registry wiring.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from engine.data import KNOWN_VENDORS, MissingCredentials, build_option_source
from engine.data.registry import build_ohlcv_source, vendor_info
from engine.data.schwab_source import SchwabAuth, SchwabCreds, SchwabSource, _f, _parse_leg
from engine.schemas import OptionRight, Timeframe


def test_schwab_is_a_known_keyed_options_and_ohlcv_vendor():
    sw = vendor_info("schwab")
    assert sw is not None
    assert sw.requires_key is True
    assert "ohlcv" in sw.capabilities and "options" in sw.capabilities
    assert any(v.vendor == "schwab" for v in KNOWN_VENDORS)


def test_creds_json_roundtrip_and_needs_refresh():
    creds = SchwabCreds(app_key="ak", app_secret="sk", redirect_uri="https://x")
    assert creds.needs_refresh is True  # no access token yet
    again = SchwabCreds.from_json(creds.to_json())
    assert again.app_key == "ak" and again.app_secret == "sk"
    again.access_token = "tok"
    again.expires_at = datetime.now(UTC).timestamp() + 3600
    assert again.needs_refresh is False
    again.expires_at = datetime.now(UTC).timestamp() + 10  # within the 60s skew
    assert again.needs_refresh is True


def test_authorize_url_contains_client_id_and_redirect():
    url = SchwabAuth.authorize_url("APPKEY", "https://127.0.0.1:8182")
    assert url.startswith("https://api.schwabapi.com/v1/oauth/authorize?")
    assert "client_id=APPKEY" in url
    assert "redirect_uri=https%3A%2F%2F127.0.0.1%3A8182" in url


def test_refresh_without_token_raises():
    with pytest.raises(MissingCredentials):
        SchwabAuth.refresh(SchwabCreds(app_key="ak", app_secret="sk"))


def test_sentinel_handling():
    assert _f(-999.0) == 0.0
    assert _f("NaN") == 0.0
    assert _f(0.42) == 0.42


def test_parse_leg_with_real_greeks():
    as_of = datetime(2026, 6, 26, tzinfo=UTC)
    leg = {
        "strikePrice": 500.0,
        "bid": 1.2,
        "ask": 1.3,
        "last": 1.25,
        "totalVolume": 1000,
        "openInterest": 5000,
        "volatility": 18.5,
        "delta": 0.45,
        "gamma": 0.03,
        "theta": -0.05,
        "vega": 0.1,
        "rho": 0.01,
        "expirationDate": "2026-06-27T20:00:00.000+00:00",
    }
    oc = _parse_leg(leg, "SPY", OptionRight.CALL, as_of)
    assert oc.right is OptionRight.CALL
    assert oc.greeks is not None and oc.greeks.computed is False
    assert oc.greeks.delta == 0.45
    assert oc.iv is not None
    assert abs(oc.iv - 0.185) < 1e-9
    assert oc.open_interest == 5000
    assert oc.expiry.isoformat() == "2026-06-27"


def test_parse_leg_drops_sentinel_greeks():
    as_of = datetime(2026, 6, 26, tzinfo=UTC)
    leg = {
        "strikePrice": 500.0,
        "delta": -999.0,
        "volatility": -999.0,
        "expirationDate": "2026-06-27T20:00:00.000+00:00",
    }
    oc = _parse_leg(leg, "SPY", OptionRight.PUT, as_of)
    assert oc.greeks is None
    assert oc.iv is None


def test_source_requires_token():
    with pytest.raises(MissingCredentials):
        SchwabSource("")


def test_get_option_chain_parses_both_sides(monkeypatch):
    src = SchwabSource("dummy-token")
    payload = {
        "underlying": {"last": 500.0},
        "callExpDateMap": {
            "2026-06-27:1": {
                "500.0": [
                    {
                        "strikePrice": 500.0,
                        "delta": 0.5,
                        "gamma": 0.02,
                        "theta": -0.04,
                        "vega": 0.1,
                        "rho": 0.0,
                        "volatility": 20.0,
                        "openInterest": 100,
                        "totalVolume": 10,
                        "bid": 1.0,
                        "ask": 1.1,
                        "last": 1.05,
                        "expirationDate": "2026-06-27T20:00:00.000+00:00",
                    }
                ]
            }
        },
        "putExpDateMap": {
            "2026-06-27:1": {
                "500.0": [
                    {
                        "strikePrice": 500.0,
                        "delta": -0.5,
                        "gamma": 0.02,
                        "theta": -0.04,
                        "vega": 0.1,
                        "rho": 0.0,
                        "volatility": 20.0,
                        "openInterest": 80,
                        "totalVolume": 8,
                        "bid": 1.0,
                        "ask": 1.1,
                        "last": 1.05,
                        "expirationDate": "2026-06-27T20:00:00.000+00:00",
                    }
                ]
            }
        },
    }
    monkeypatch.setattr(src, "_get", lambda path, **p: payload)
    chain = src.get_option_chain("SPY")
    assert chain.source == "schwab"
    assert float(chain.spot) == 500.0
    assert len(chain.contracts) == 2
    rights = {c.right for c in chain.contracts}
    assert rights == {OptionRight.CALL, OptionRight.PUT}
    assert chain.degraded is False


def test_get_ohlcv_parses_candles(monkeypatch):
    src = SchwabSource("dummy-token")
    payload = {
        "candles": [
            {
                "datetime": 1_700_000_000_000,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 100,
            },
            {
                "datetime": 1_700_086_400_000,
                "open": 1.5,
                "high": 2.5,
                "low": 1.0,
                "close": 2.0,
                "volume": 200,
            },
        ]
    }
    monkeypatch.setattr(src, "_get", lambda path, **p: payload)
    start = datetime(2026, 6, 1, tzinfo=UTC)
    ohlcv = src.get_ohlcv("SPY", Timeframe.D1, start)
    assert ohlcv.source == "schwab"
    assert len(ohlcv.bars) == 2
    assert ohlcv.bars[0].ts < ohlcv.bars[1].ts
    assert float(ohlcv.bars[1].close) == 2.0


def test_build_sources_route_to_schwab():
    with pytest.raises(MissingCredentials):
        build_ohlcv_source("schwab", api_key=None)
    with pytest.raises(MissingCredentials):
        build_option_source("schwab", api_key=None)
    ohlcv = build_ohlcv_source("schwab", api_key="tok")
    opt = build_option_source("schwab", api_key="tok")
    assert isinstance(ohlcv, SchwabSource) and isinstance(opt, SchwabSource)
