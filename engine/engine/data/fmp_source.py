"""Financial Modeling Prep (FMP) adapter — keyed equity OHLCV (the primary equity feed).

FMP provides clean adjusted daily history and intraday bars. The API key is supplied
per-call (decrypted from the encrypted Settings store). Used as the preferred equity
OHLCV source when an enabled FMP key exists, with yfinance as the keyless fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import requests

from ..schemas import OHLCV, MarketBar, Timeframe
from .base import DataSourceError, MissingCredentials, OhlcvSource

# FMP "stable" API (the v3 /historical-price-full + /profile endpoints were retired for
# new keys on 2025-08-31). Daily uses split+dividend-adjusted EOD; intraday uses the
# historical-chart series. Both take ?symbol=&from=&to=.
_BASE = "https://financialmodelingprep.com/stable"

_INTRADAY = {
    Timeframe.M1: "1min",
    Timeframe.M5: "5min",
    Timeframe.M15: "15min",
    Timeframe.M30: "30min",
    Timeframe.H1: "1hour",
    Timeframe.H4: "4hour",
}


def _to_decimal(v) -> Decimal:
    return Decimal(str(round(float(v), 6)))


class FMPSource(OhlcvSource):
    name = "fmp"

    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        if not api_key:
            raise MissingCredentials("FMP requires an API key (add it in Settings)")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, **params) -> dict | list:
        params["apikey"] = self.api_key
        try:
            resp = requests.get(f"{_BASE}/{path}", params=params, timeout=self.timeout)
        except requests.RequestException as exc:  # pragma: no cover - network
            raise DataSourceError(f"FMP request failed: {exc}") from exc
        if resp.status_code in (401, 403):
            raise MissingCredentials("FMP rejected the API key")
        if resp.status_code == 429:
            raise DataSourceError("FMP rate limit hit (429)")
        if resp.status_code >= 400:
            raise DataSourceError(f"FMP {path} -> HTTP {resp.status_code}")
        return resp.json()

    def get_ohlcv(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime | None = None
    ) -> OHLCV:
        window = {
            "symbol": symbol,
            "from": start.date().isoformat(),
            "to": (end or datetime.now(UTC)).date().isoformat(),
        }
        if timeframe in _INTRADAY:
            rows = self._get(f"historical-chart/{_INTRADAY[timeframe]}", **window)
            records = rows if isinstance(rows, list) else []
            adjusted = False
        else:
            # split+dividend-adjusted daily EOD (adjOpen/adjHigh/adjLow/adjClose).
            rows = self._get("historical-price-eod/dividend-adjusted", **window)
            records = rows if isinstance(rows, list) else []
            adjusted = True

        bars: list[MarketBar] = []
        for r in records:
            ts = _parse_ts(r.get("date"))
            if ts is None:
                continue
            try:
                bars.append(
                    MarketBar(
                        symbol=symbol,
                        timeframe=timeframe,
                        ts=ts,
                        open=_to_decimal(r.get("adjOpen", r.get("open"))),
                        high=_to_decimal(r.get("adjHigh", r.get("high"))),
                        low=_to_decimal(r.get("adjLow", r.get("low"))),
                        close=_to_decimal(r.get("adjClose", r.get("close"))),
                        volume=int(r.get("volume", 0) or 0),
                        source=self.name,
                        is_adjusted=adjusted,
                    )
                )
            except Exception:
                continue
        # FMP returns newest-first; the OHLCV contract needs strictly increasing ts.
        bars.sort(key=lambda b: b.ts)
        return OHLCV(symbol=symbol, timeframe=timeframe, source=self.name, bars=bars)


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None
