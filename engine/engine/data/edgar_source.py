"""SEC EDGAR adapter (keyless) — corporate-insider Form 4 transactions.

EDGAR is free but requires a descriptive User-Agent. Flow: ticker -> CIK (company
tickers map) -> recent submissions (filter Form 4) -> parse each Form 4 ownership XML
for non-derivative transactions. Defensive throughout; partial parses are skipped.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from functools import lru_cache

import requests

from ..schemas import InsiderTransaction, Side
from .base import DataSourceError, InsiderSource

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
_DEFAULT_UA = "stock-wizard research (contact: welberribeirodrums@gmail.com)"


class EdgarSource(InsiderSource):
    name = "edgar"

    def __init__(self, user_agent: str | None = None, timeout: float = 20.0, max_filings: int = 40):
        self.headers = {"User-Agent": user_agent or _DEFAULT_UA, "Accept-Encoding": "gzip"}
        self.timeout = timeout
        self.max_filings = max_filings

    def _get_json(self, url: str) -> dict:
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        except requests.RequestException as exc:  # pragma: no cover - network
            raise DataSourceError(f"EDGAR request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise DataSourceError(f"EDGAR {url} -> HTTP {resp.status_code}")
        return resp.json()

    @lru_cache(maxsize=1)
    def _ticker_map(self) -> dict[str, str]:
        data = self._get_json(_TICKERS_URL)
        out: dict[str, str] = {}
        for row in data.values():
            out[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
        return out

    def _cik(self, symbol: str) -> str | None:
        return self._ticker_map().get(symbol.upper())

    def get_insider_transactions(
        self, symbol: str, since: date | None = None
    ) -> list[InsiderTransaction]:
        cik = self._cik(symbol)
        if cik is None:
            return []
        subs = self._get_json(_SUBMISSIONS_URL.format(cik=cik))
        recent = subs.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accns = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])

        out: list[InsiderTransaction] = []
        seen = 0
        for form, accn, doc in zip(forms, accns, docs):
            if form != "4":
                continue
            seen += 1
            if seen > self.max_filings:
                break
            acc_nodash = accn.replace("-", "")
            url = _ARCHIVE.format(cik=int(cik), acc=acc_nodash, doc=doc)
            try:
                out.extend(self._parse_form4(symbol, url, since))
            except Exception:
                continue
        return out

    def _parse_form4(
        self, symbol: str, url: str, since: date | None
    ) -> list[InsiderTransaction]:
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        except requests.RequestException:  # pragma: no cover - network
            return []
        if resp.status_code >= 400 or not resp.content.strip().startswith(b"<"):
            return []

        root = ET.fromstring(resp.content)
        owner = root.findtext(".//reportingOwner/reportingOwnerId/rptOwnerName") or "unknown"
        title = root.findtext(".//reportingOwner/reportingOwnerRelationship/officerTitle")
        filing_date = _txt_date(root.findtext(".//periodOfReport"))

        out: list[InsiderTransaction] = []
        for tx in root.findall(".//nonDerivativeTransaction"):
            tdate = _txt_date(tx.findtext(".//transactionDate/value"))
            if tdate is None or (since and tdate < since):
                continue
            code = tx.findtext(".//transactionCoding/transactionCode")
            shares = _txt_float(tx.findtext(".//transactionShares/value"))
            price = _txt_decimal(tx.findtext(".//transactionPricePerShare/value"))
            ad = tx.findtext(".//transactionAcquiredDisposedCode/value")
            side = Side.LONG if ad == "A" else Side.SHORT if ad == "D" else Side.NEUTRAL
            held = _txt_float(tx.findtext(".//sharesOwnedFollowingTransaction/value"))
            value = Decimal(shares) * price if (shares and price) else None
            out.append(
                InsiderTransaction(
                    symbol=symbol,
                    insider_name=owner,
                    title=title,
                    transaction_date=tdate,
                    filing_date=filing_date,
                    transaction_code=code,
                    side=side,
                    shares=shares or 0.0,
                    price=price,
                    value=value,
                    shares_held_after=held,
                    source=self.name,
                )
            )
        return out


def _txt_date(v: str | None) -> date | None:
    try:
        return date.fromisoformat(v[:10]) if v else None
    except (ValueError, TypeError):
        return None


def _txt_float(v: str | None) -> float | None:
    try:
        return float(v) if v else None
    except (ValueError, TypeError):
        return None


def _txt_decimal(v: str | None) -> Decimal | None:
    try:
        return Decimal(v) if v else None
    except (ValueError, TypeError):
        return None
