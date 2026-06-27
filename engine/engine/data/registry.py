"""Vendor registry — known vendors (for the Settings panel) and adapter resolution.

``KNOWN_VENDORS`` tells the dashboard which vendors exist, which need an API key, and
what each can provide. The ``build_*`` helpers construct an adapter given an optional
decrypted key. yfinance and SEC EDGAR need no key; Finnhub and future paid vendors do.
"""

from __future__ import annotations

from .base import (
    Capability,
    CongressSource,
    InsiderSource,
    MissingCredentials,
    OhlcvSource,
    OptionSource,
    VendorInfo,
)

KNOWN_VENDORS: list[VendorInfo] = [
    VendorInfo(
        vendor="yfinance",
        label="Yahoo Finance",
        requires_key=False,
        capabilities=[Capability.OHLCV, Capability.OPTIONS],
        notes="Free default. Real OHLCV; option greeks computed by the engine.",
    ),
    VendorInfo(
        vendor="sec_edgar",
        label="SEC EDGAR",
        requires_key=False,
        capabilities=[Capability.INSIDER],
        docs_url="https://www.sec.gov/edgar",
        notes="Keyless. Corporate-insider Form 4 transactions, from the source.",
    ),
    VendorInfo(
        vendor="finnhub",
        label="Finnhub",
        requires_key=True,
        capabilities=[
            Capability.INSIDER,
            Capability.CONGRESS,
            Capability.EARNINGS,
            Capability.NEWS,
        ],
        docs_url="https://finnhub.io/docs/api",
        notes="Insider + congressional trades, earnings calendar, company news.",
    ),
    VendorInfo(
        vendor="fmp",
        label="Financial Modeling Prep (FMP)",
        requires_key=True,
        capabilities=[Capability.OHLCV, Capability.EARNINGS, Capability.NEWS],
        docs_url="https://site.financialmodelingprep.com/developer/docs",
        notes="Primary equity feed: adjusted daily + intraday OHLCV. Preferred over yfinance when keyed.",
    ),
    VendorInfo(
        vendor="schwab",
        label="Charles Schwab",
        requires_key=True,
        capabilities=[Capability.OHLCV, Capability.OPTIONS],
        docs_url="https://developer.schwab.com",
        notes="OAuth2 (app key+secret → authorize → token). Real option chains with vendor "
        "greeks/OI/IV — preferred for the gamma engine — plus equity OHLCV.",
    ),
    # --- adapter slots for paid market-data vendors (plug in later) ---
    VendorInfo(
        "polygon", "Polygon.io", True, [Capability.OHLCV, Capability.OPTIONS], notes="planned"
    ),
    VendorInfo("tradier", "Tradier", True, [Capability.OHLCV, Capability.OPTIONS], notes="planned"),
    VendorInfo(
        "theta", "Theta Data", True, [Capability.OPTIONS, Capability.INTERNALS], notes="planned"
    ),
    VendorInfo("orats", "ORATS", True, [Capability.OPTIONS], notes="planned"),
    VendorInfo("cboe", "CBOE", True, [Capability.OPTIONS, Capability.INTERNALS], notes="planned"),
]

_BY_NAME = {v.vendor: v for v in KNOWN_VENDORS}


def vendor_info(name: str) -> VendorInfo | None:
    return _BY_NAME.get(name)


def build_ohlcv_source(vendor: str = "yfinance", api_key: str | None = None) -> OhlcvSource:
    if vendor == "yfinance":
        from .yfinance_source import YFinanceSource

        return YFinanceSource()
    if vendor == "fmp":
        from .fmp_source import FMPSource

        if not api_key:
            raise MissingCredentials("FMP requires an API key")
        return FMPSource(api_key)
    if vendor == "schwab":
        from .schwab_source import SchwabSource

        if not api_key:
            raise MissingCredentials("Schwab requires an access token (authorize in Settings)")
        return SchwabSource(api_key)
    raise MissingCredentials(f"No OHLCV adapter wired for vendor '{vendor}'")


def build_option_source(vendor: str = "yfinance", api_key: str | None = None) -> OptionSource:
    if vendor == "yfinance":
        from .yfinance_source import YFinanceSource

        return YFinanceSource()
    if vendor == "schwab":
        from .schwab_source import SchwabSource

        if not api_key:
            raise MissingCredentials("Schwab requires an access token (authorize in Settings)")
        return SchwabSource(api_key)
    raise MissingCredentials(f"No option adapter wired for vendor '{vendor}'")


def build_insider_source(vendor: str = "sec_edgar", api_key: str | None = None) -> InsiderSource:
    if vendor == "sec_edgar":
        from .edgar_source import EdgarSource

        return EdgarSource()
    if vendor == "finnhub":
        from .finnhub_source import FinnhubSource

        if not api_key:
            raise MissingCredentials("Finnhub insider data requires an API key")
        return FinnhubSource(api_key)
    raise MissingCredentials(f"No insider adapter wired for vendor '{vendor}'")


def build_congress_source(vendor: str = "finnhub", api_key: str | None = None) -> CongressSource:
    if vendor == "finnhub":
        from .finnhub_source import FinnhubSource

        if not api_key:
            raise MissingCredentials("Finnhub congressional data requires an API key")
        return FinnhubSource(api_key)
    raise MissingCredentials(f"No congress adapter wired for vendor '{vendor}'")
