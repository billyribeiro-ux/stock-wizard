"""Charles Schwab Trader API adapter — OAuth2 equity OHLCV + option chains with greeks.

Schwab (the former TD Ameritrade API) uses 3-legged OAuth2: an app key + secret obtain
an authorization code (browser consent), which exchanges for an access token (~30 min)
and a refresh token (~7 days). Credentials are stored as one encrypted JSON bundle in
the vendor-key store; ``SchwabAuth`` builds the authorize URL, exchanges the code, and
refreshes the access token. ``SchwabSource`` then serves price history and — importantly
for the gamma engine — REAL option chains with vendor greeks/OI/IV.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

import requests

from ..schemas import (
    OHLCV,
    Greeks,
    MarketBar,
    OptionChain,
    OptionContract,
    OptionRight,
    Timeframe,
)
from .base import DataSourceError, MissingCredentials, OhlcvSource, OptionSource

_AUTH = "https://api.schwabapi.com/v1/oauth/authorize"
_TOKEN = "https://api.schwabapi.com/v1/oauth/token"
_MARKETDATA = "https://api.schwabapi.com/marketdata/v1"

_FREQ = {
    Timeframe.M1: ("minute", 1),
    Timeframe.M5: ("minute", 5),
    Timeframe.M15: ("minute", 15),
    Timeframe.M30: ("minute", 30),
    Timeframe.D1: ("daily", 1),
    Timeframe.W1: ("weekly", 1),
    Timeframe.MO1: ("monthly", 1),
}


@dataclass
class SchwabCreds:
    """The encrypted-at-rest Schwab credential bundle."""

    app_key: str
    app_secret: str
    redirect_uri: str = "https://127.0.0.1:8182"
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0  # epoch seconds when the access token expires

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> SchwabCreds:
        return cls(**json.loads(raw))

    @property
    def needs_refresh(self) -> bool:
        return (not self.access_token) or time.time() >= (self.expires_at - 60)


class SchwabAuth:
    """OAuth2 helpers — pure URL/token operations, no storage."""

    @staticmethod
    def authorize_url(app_key: str, redirect_uri: str) -> str:
        from urllib.parse import urlencode

        q = urlencode({"client_id": app_key, "redirect_uri": redirect_uri})
        return f"{_AUTH}?{q}"

    @staticmethod
    def _basic(app_key: str, app_secret: str) -> str:
        return base64.b64encode(f"{app_key}:{app_secret}".encode()).decode()

    @classmethod
    def _token_request(cls, creds: SchwabCreds, data: dict) -> SchwabCreds:
        headers = {
            "Authorization": f"Basic {cls._basic(creds.app_key, creds.app_secret)}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            resp = requests.post(_TOKEN, headers=headers, data=data, timeout=20)
        except requests.RequestException as exc:  # pragma: no cover - network
            raise DataSourceError(f"Schwab token request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise MissingCredentials(f"Schwab token exchange failed ({resp.status_code})")
        tok = resp.json()
        creds.access_token = tok.get("access_token", "")
        # Schwab returns a fresh refresh_token only on the initial exchange.
        if tok.get("refresh_token"):
            creds.refresh_token = tok["refresh_token"]
        creds.expires_at = time.time() + float(tok.get("expires_in", 1800))
        return creds

    @classmethod
    def exchange_code(cls, creds: SchwabCreds, code: str) -> SchwabCreds:
        return cls._token_request(
            creds,
            {"grant_type": "authorization_code", "code": code, "redirect_uri": creds.redirect_uri},
        )

    @classmethod
    def refresh(cls, creds: SchwabCreds) -> SchwabCreds:
        if not creds.refresh_token:
            raise MissingCredentials("Schwab refresh token missing — re-authorize")
        return cls._token_request(
            creds, {"grant_type": "refresh_token", "refresh_token": creds.refresh_token}
        )


def _to_decimal(v):
    from decimal import Decimal

    return Decimal(str(round(float(v), 6))) if v is not None else None


class SchwabSource(OhlcvSource, OptionSource):
    name = "schwab"

    def __init__(self, access_token: str, timeout: float = 20.0) -> None:
        if not access_token:
            raise MissingCredentials("Schwab requires a valid access token (authorize in Settings)")
        self.access_token = access_token
        self.timeout = timeout

    def _get(self, path: str, **params) -> dict:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            resp = requests.get(
                f"{_MARKETDATA}/{path}", headers=headers, params=params, timeout=self.timeout
            )
        except requests.RequestException as exc:  # pragma: no cover - network
            raise DataSourceError(f"Schwab request failed: {exc}") from exc
        if resp.status_code == 401:
            raise MissingCredentials("Schwab access token expired/invalid")
        if resp.status_code >= 400:
            raise DataSourceError(f"Schwab {path} -> HTTP {resp.status_code}")
        return resp.json()

    def get_ohlcv(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime | None = None
    ) -> OHLCV:
        ftype, fval = _FREQ.get(timeframe, ("daily", 1))
        params = {
            "symbol": symbol,
            "frequencyType": ftype,
            "frequency": fval,
            "startDate": int(start.timestamp() * 1000),
            "endDate": int((end or datetime.now(UTC)).timestamp() * 1000),
            "needExtendedHoursData": "false",
        }
        params["periodType"] = "day" if ftype == "minute" else "year"
        payload = self._get("pricehistory", **params)
        bars: list[MarketBar] = []
        for c in payload.get("candles", []):
            ts = datetime.fromtimestamp(c["datetime"] / 1000, tz=UTC)
            try:
                bars.append(
                    MarketBar(
                        symbol=symbol,
                        timeframe=timeframe,
                        ts=ts,
                        open=_to_decimal(c["open"]),
                        high=_to_decimal(c["high"]),
                        low=_to_decimal(c["low"]),
                        close=_to_decimal(c["close"]),
                        volume=int(c.get("volume", 0) or 0),
                        source=self.name,
                        is_adjusted=True,
                    )
                )
            except Exception:
                continue
        bars.sort(key=lambda b: b.ts)
        return OHLCV(symbol=symbol, timeframe=timeframe, source=self.name, bars=bars)

    def get_option_chain(self, underlying: str, expiry: date | None = None) -> OptionChain:
        params = {"symbol": underlying, "contractType": "ALL", "includeUnderlyingQuote": "true"}
        if expiry is not None:
            params["fromDate"] = expiry.isoformat()
            params["toDate"] = expiry.isoformat()
        payload = self._get("chains", **params)
        as_of = datetime.now(UTC)
        spot = (
            _to_decimal((payload.get("underlying") or {}).get("last"))
            or _to_decimal(payload.get("underlyingPrice"))
            or _to_decimal(0)
        )
        contracts: list[OptionContract] = []
        for map_key, right in (
            ("callExpDateMap", OptionRight.CALL),
            ("putExpDateMap", OptionRight.PUT),
        ):
            for _exp, strikes in (payload.get(map_key) or {}).items():
                for _strike, legs in strikes.items():
                    for o in legs:
                        contracts.append(_parse_leg(o, underlying, right, as_of))
        degraded = spot is None or spot <= 0 or not contracts
        return OptionChain(
            underlying=underlying,
            as_of=as_of,
            spot=spot or _to_decimal(0),
            contracts=contracts,
            source=self.name,
            degraded=degraded,
        )


def _parse_leg(o: dict, underlying: str, right: OptionRight, as_of: datetime) -> OptionContract:
    raw_iv = _f(o.get("volatility"))  # 0.0 for None / "NaN" / -999.0 sentinels
    iv = raw_iv / 100.0 if raw_iv > 0 else None
    greeks = None
    if o.get("delta") not in (None, "NaN", -999.0):
        greeks = Greeks(
            delta=_f(o.get("delta")),
            gamma=_f(o.get("gamma")),
            theta=_f(o.get("theta")),
            vega=_f(o.get("vega")),
            rho=_f(o.get("rho")),
            iv=iv or 0.0,
            computed=False,
        )
    exp = o.get("expirationDate", "")[:10]
    return OptionContract(
        underlying=underlying,
        expiry=date.fromisoformat(exp) if exp else as_of.date(),
        strike=_to_decimal(o.get("strikePrice")),
        right=right,
        bid=_to_decimal(o.get("bid")),
        ask=_to_decimal(o.get("ask")),
        last=_to_decimal(o.get("last")),
        volume=int(o.get("totalVolume", 0) or 0),
        open_interest=int(o.get("openInterest", 0) or 0),
        iv=iv,
        greeks=greeks,
        as_of=as_of,
    )


def _f(v) -> float:
    import math

    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if (f == -999.0 or math.isnan(f) or math.isinf(f)) else f
