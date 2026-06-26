"""yfinance adapter — the free default for OHLCV and option chains.

OHLCV is real. Option greeks are NOT provided by yfinance, so the chain is returned
with IV from yfinance where present (else solved downstream) and ``computed=True``
greeks are filled by the feature factory. SPX 0DTE coverage on yfinance is thin, so
the gamma scanner defaults to SPY (see scanners/spx_gamma_command.py).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from ..schemas import (
    OHLCV,
    MarketBar,
    OptionChain,
    OptionContract,
    OptionRight,
    Timeframe,
)
from .base import DataSourceError, OhlcvSource, OptionSource

_INTERVAL = {
    Timeframe.M1: "1m",
    Timeframe.M5: "5m",
    Timeframe.M15: "15m",
    Timeframe.M30: "30m",
    Timeframe.H1: "60m",
    Timeframe.H4: "60m",  # yfinance has no 4h; caller may resample
    Timeframe.D1: "1d",
    Timeframe.W1: "1wk",
    Timeframe.MO1: "1mo",
}


def _to_decimal(v) -> Decimal:
    return Decimal(str(round(float(v), 6)))


class YFinanceSource(OhlcvSource, OptionSource):
    name = "yfinance"

    def __init__(self) -> None:
        import yfinance  # noqa: F401  (import-time check)

    def get_ohlcv(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime | None = None
    ) -> OHLCV:
        import yfinance as yf

        interval = _INTERVAL[timeframe]
        try:
            df = yf.download(
                symbol,
                start=start.date().isoformat(),
                end=end.date().isoformat() if end else None,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as exc:  # pragma: no cover - network
            raise DataSourceError(f"yfinance download failed for {symbol}: {exc}") from exc

        if df is None or df.empty:
            return OHLCV(symbol=symbol, timeframe=timeframe, source=self.name, bars=[])

        # yfinance may return a MultiIndex column frame for single tickers.
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)

        bars: list[MarketBar] = []
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime()
            ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
            try:
                bar = MarketBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=ts,
                    open=_to_decimal(row["Open"]),
                    high=_to_decimal(row["High"]),
                    low=_to_decimal(row["Low"]),
                    close=_to_decimal(row["Close"]),
                    volume=int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                    source=self.name,
                    is_adjusted=False,
                )
            except Exception:
                continue
            bars.append(bar)

        return OHLCV(symbol=symbol, timeframe=timeframe, source=self.name, bars=bars)

    def get_option_chain(self, underlying: str, expiry: date | None = None) -> OptionChain:
        import yfinance as yf

        tkr = yf.Ticker(underlying)
        try:
            expiries = tkr.options
        except Exception as exc:  # pragma: no cover - network
            raise DataSourceError(f"yfinance options unavailable for {underlying}: {exc}") from exc

        if not expiries:
            now = datetime.now(UTC)
            return OptionChain(
                underlying=underlying, as_of=now, spot=Decimal(0), contracts=[], degraded=True
            )

        target = expiry.isoformat() if expiry else expiries[0]
        if target not in expiries:
            target = expiries[0]

        oc = tkr.option_chain(target)
        spot = self._spot(tkr)
        as_of = datetime.now(UTC)
        exp_date = date.fromisoformat(target)

        contracts: list[OptionContract] = []
        missing = 0
        for df, right in ((oc.calls, OptionRight.CALL), (oc.puts, OptionRight.PUT)):
            for _, row in df.iterrows():
                iv = float(row.get("impliedVolatility", 0) or 0)
                oi = int(row.get("openInterest", 0) or 0)
                if oi <= 0:
                    missing += 1
                contracts.append(
                    OptionContract(
                        underlying=underlying,
                        expiry=exp_date,
                        strike=_to_decimal(row["strike"]),
                        right=right,
                        bid=_to_decimal(row["bid"]) if row.get("bid") else None,
                        ask=_to_decimal(row["ask"]) if row.get("ask") else None,
                        last=_to_decimal(row["lastPrice"]) if row.get("lastPrice") else None,
                        volume=int(row.get("volume", 0) or 0),
                        open_interest=oi,
                        iv=iv if iv > 0 else None,
                        as_of=as_of,
                    )
                )

        degraded = spot <= 0 or missing > len(contracts) // 2
        return OptionChain(
            underlying=underlying,
            as_of=as_of,
            spot=spot,
            contracts=contracts,
            source=self.name,
            degraded=degraded,
        )

    @staticmethod
    def _spot(tkr) -> Decimal:
        try:
            fi = tkr.fast_info
            px = fi.get("last_price") or fi.get("lastPrice")
            if px:
                return _to_decimal(px)
        except Exception:
            pass
        try:
            hist = tkr.history(period="1d")
            if not hist.empty:
                return _to_decimal(hist["Close"].iloc[-1])
        except Exception:
            pass
        return Decimal(0)
