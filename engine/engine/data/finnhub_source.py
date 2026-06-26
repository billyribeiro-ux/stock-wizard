"""Finnhub adapter (keyed) — insider transactions, congressional trades, earnings, news.

The API key is supplied per-call via SourceContext (decrypted from the encrypted
Settings store). Endpoints degrade gracefully: a missing key raises MissingCredentials;
a premium-gated endpoint returning empty is treated as "no data", not an error.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import requests

from ..schemas import (
    CongressTrade,
    EarningsEvent,
    InsiderTransaction,
    NewsItem,
    Side,
)
from .base import (
    CongressSource,
    DataSourceError,
    EarningsSource,
    InsiderSource,
    MissingCredentials,
    NewsSource,
)

_BASE = "https://finnhub.io/api/v1"


def _side_from_code(code: str | None) -> Side:
    if not code:
        return Side.NEUTRAL
    c = code.upper()
    if c.startswith("P") or c in {"BUY", "A"}:
        return Side.LONG
    if c.startswith("S") or c == "SELL" or c == "D":
        return Side.SHORT
    return Side.NEUTRAL


class FinnhubSource(InsiderSource, CongressSource, EarningsSource, NewsSource):
    name = "finnhub"

    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        if not api_key:
            raise MissingCredentials("Finnhub requires an API key (add it in Settings)")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, **params) -> dict | list:
        params["token"] = self.api_key
        try:
            resp = requests.get(f"{_BASE}/{path}", params=params, timeout=self.timeout)
        except requests.RequestException as exc:  # pragma: no cover - network
            raise DataSourceError(f"Finnhub request failed: {exc}") from exc
        if resp.status_code == 401:
            raise MissingCredentials("Finnhub rejected the API key (401)")
        if resp.status_code >= 400:
            raise DataSourceError(f"Finnhub {path} -> HTTP {resp.status_code}")
        return resp.json()

    def get_insider_transactions(
        self, symbol: str, since: date | None = None
    ) -> list[InsiderTransaction]:
        payload = self._get("stock/insider-transactions", symbol=symbol)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        out: list[InsiderTransaction] = []
        for r in rows:
            try:
                tdate = date.fromisoformat(r["transactionDate"])
            except (KeyError, ValueError):
                continue
            if since and tdate < since:
                continue
            shares = float(r.get("share", r.get("change", 0)) or 0)
            price = r.get("transactionPrice")
            out.append(
                InsiderTransaction(
                    symbol=symbol,
                    insider_name=r.get("name", "unknown"),
                    transaction_date=tdate,
                    filing_date=_safe_date(r.get("filingDate")),
                    transaction_code=r.get("transactionCode"),
                    side=_side_from_code(r.get("transactionCode")),
                    shares=abs(shares),
                    price=Decimal(str(price)) if price else None,
                    shares_held_after=_safe_float(r.get("sharesHeld")),
                    source=self.name,
                )
            )
        return out

    def get_congress_trades(self, symbol: str, since: date | None = None) -> list[CongressTrade]:
        payload = self._get("stock/congressional-trading", symbol=symbol)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        out: list[CongressTrade] = []
        for r in rows:
            tdate = _safe_date(r.get("transactionDate"))
            if tdate is None or (since and tdate < since):
                continue
            out.append(
                CongressTrade(
                    symbol=symbol,
                    representative=r.get("name", "unknown"),
                    chamber=r.get("chamber"),
                    transaction_date=tdate,
                    filing_date=_safe_date(r.get("filingDate")),
                    side=_side_from_code(r.get("transactionType")),
                    amount_low=_safe_decimal(r.get("amountFrom")),
                    amount_high=_safe_decimal(r.get("amountTo")),
                    asset_name=r.get("assetName"),
                    source=self.name,
                )
            )
        return out

    def get_earnings(self, symbol: str, since: date | None = None) -> list[EarningsEvent]:
        frm = since.isoformat() if since else "2020-01-01"
        to = date.today().isoformat()
        payload = self._get("calendar/earnings", symbol=symbol, **{"from": frm, "to": to})
        rows = payload.get("earningsCalendar", []) if isinstance(payload, dict) else []
        out: list[EarningsEvent] = []
        for r in rows:
            edate = _safe_date(r.get("date"))
            if edate is None:
                continue
            out.append(
                EarningsEvent(
                    symbol=symbol,
                    date=edate,
                    hour=r.get("hour"),
                    eps_estimate=_safe_float(r.get("epsEstimate")),
                    eps_actual=_safe_float(r.get("epsActual")),
                    revenue_estimate=_safe_float(r.get("revenueEstimate")),
                    revenue_actual=_safe_float(r.get("revenueActual")),
                    source=self.name,
                )
            )
        return out

    def get_news(self, symbol: str, since: date | None = None) -> list[NewsItem]:
        frm = since.isoformat() if since else date.today().isoformat()
        to = date.today().isoformat()
        payload = self._get("company-news", symbol=symbol, **{"from": frm, "to": to})
        rows = payload if isinstance(payload, list) else []
        out: list[NewsItem] = []
        for r in rows:
            ts = r.get("datetime")
            published = (
                datetime.fromtimestamp(ts, tz=UTC)
                if isinstance(ts, (int, float))
                else datetime.now(UTC)
            )
            out.append(
                NewsItem(
                    symbol=symbol,
                    headline=r.get("headline", ""),
                    summary=r.get("summary"),
                    url=r.get("url"),
                    published_at=published,
                    category=r.get("category"),
                    source=self.name,
                )
            )
        return out


def _safe_date(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_decimal(v) -> Decimal | None:
    try:
        return Decimal(str(v)) if v is not None else None
    except (TypeError, ValueError):
        return None
