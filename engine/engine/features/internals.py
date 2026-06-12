"""Institutional market internals, computed from first principles.

Large institutions watch internals computed over the market's constituents — not a
magic feed. Given a universe basket of liquid names this module computes the same
numbers the institutional desks do:

- Advance/Decline: advancers, decliners, net advances, the cumulative **A/D line**
- **UVOL/DVOL**: up-volume vs down-volume (and the VOLD differential)
- **TRIN (Arms Index)** = (advancers/decliners) / (UVOL/DVOL)
- **McClellan Oscillator** = EMA19(net adv ratio) - EMA39(net adv ratio), and the
  **McClellan Summation Index** (cumulative oscillator)
- **% above 20/50/200-bar moving averages** (participation breadth)
- **Net new highs/lows** over a rolling window (52-week proxy at daily resolution)
- **Zweig Breadth Thrust**: 10-bar EMA of adv/(adv+dec) crossing 0.40 → 0.615
- **Put/Call ratio** from a live option chain (volume-based)
- **VIX term structure**: VIX9D/VIX/VIX3M contango vs backwardation

Only intraday TICK (NYSE up-tick minus down-tick prints) genuinely requires an
exchange feed; everything here runs off constituent OHLCV + chains.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..schemas import OHLCV, OptionChain, OptionRight
from .base import ohlcv_to_frame

# A liquid mega-cap default basket (configurable per scan) — breadth computed over it.
DEFAULT_UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "BRK-B",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "JNJ",
    "WMT",
    "PG",
    "MA",
    "AVGO",
    "HD",
    "COST",
    "ORCL",
    "MRK",
    "ABBV",
    "CVX",
    "KO",
    "PEP",
    "BAC",
    "AMD",
    "CRM",
    "NFLX",
    "DIS",
]

RISK_RATIO_PAIRS = [
    ("RSP", "SPY", "equal_weight_vs_cap"),  # broad participation vs mega-cap
    ("SPHB", "SPLV", "high_beta_vs_low_vol"),  # risk appetite
    ("XLY", "XLP", "discretionary_vs_staples"),  # offense vs defense
    ("IWM", "SPY", "small_vs_large"),  # risk breadth down the cap scale
    ("HYG", "IEF", "credit_vs_treasuries"),  # credit risk appetite
]

VOL_TERM_SYMBOLS = ["^VIX9D", "^VIX", "^VIX3M"]


def _aligned_frames(universe: dict[str, OHLCV], min_bars: int = 2) -> dict[str, pd.DataFrame]:
    out = {}
    for sym, ohlcv in universe.items():
        df = ohlcv_to_frame(ohlcv)
        if len(df) >= min_bars:
            out[sym] = df
    return out


@dataclass
class BreadthSnapshot:
    n_symbols: int
    advancers: int
    decliners: int
    net_advances: int
    ad_ratio: float  # advancers / decliners
    uvol: float  # volume in advancing names
    dvol: float  # volume in declining names
    vold: float  # uvol - dvol (volume differential)
    trin: float | None  # Arms Index
    ad_line: list[float]  # cumulative A/D line (last 60 points)
    mcclellan_osc: float | None
    mcclellan_sum: float | None
    pct_above_ma20: float | None
    pct_above_ma50: float | None
    pct_above_ma200: float | None
    net_new_highs: int  # NH - NL over the rolling window
    zweig_emaratio: float | None  # 10-bar EMA of adv/(adv+dec)
    zweig_thrust: bool  # crossed from <0.40 to >0.615 within 10 bars
    meta: dict = field(default_factory=dict)


def compute_breadth(universe: dict[str, OHLCV], nhnl_window: int = 252) -> BreadthSnapshot | None:
    frames = _aligned_frames(universe, min_bars=3)
    if len(frames) < 5:
        return None

    # --- last-bar advance/decline + up/down volume ---
    advancers = decliners = 0
    uvol = dvol = 0.0
    above20 = above50 = above200 = 0
    n20 = n50 = n200 = 0
    nh = nl = 0
    for df in frames.values():
        last, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
        vol = float(df["volume"].iloc[-1])
        if last > prev:
            advancers += 1
            uvol += vol
        elif last < prev:
            decliners += 1
            dvol += vol
        for period, counter in ((20, "20"), (50, "50"), (200, "200")):
            if len(df) >= period:
                ma = float(df["close"].iloc[-period:].mean())
                if counter == "20":
                    n20 += 1
                    above20 += last > ma
                elif counter == "50":
                    n50 += 1
                    above50 += last > ma
                else:
                    n200 += 1
                    above200 += last > ma
        win = df["close"].iloc[-min(nhnl_window, len(df)) :]
        if last >= float(win.max()):
            nh += 1
        elif last <= float(win.min()):
            nl += 1

    ad_ratio = advancers / max(decliners, 1)
    vol_ratio = uvol / max(dvol, 1e-9)
    trin = (ad_ratio / vol_ratio) if vol_ratio > 0 else None

    # --- time series internals over the aligned history ---
    # net-advance ratio per bar: (adv - dec) / total, on common timestamps
    closes = pd.DataFrame({s: f["close"] for s, f in frames.items()}).dropna(how="all")
    diff = closes.diff()
    adv_t = (diff > 0).sum(axis=1)
    dec_t = (diff < 0).sum(axis=1)
    total_t = (adv_t + dec_t).replace(0, np.nan)
    net_ratio = ((adv_t - dec_t) / total_t).fillna(0.0)
    ad_line = (adv_t - dec_t).cumsum()

    mcc_osc = mcc_sum = None
    if len(net_ratio) >= 40:
        ema19 = net_ratio.ewm(span=19, adjust=False).mean()
        ema39 = net_ratio.ewm(span=39, adjust=False).mean()
        osc = (ema19 - ema39) * 1000  # scaled, conventional presentation
        mcc_osc = float(osc.iloc[-1])
        mcc_sum = float(osc.cumsum().iloc[-1])

    zweig_ratio = None
    thrust = False
    if len(adv_t) >= 12:
        ratio = (adv_t / (adv_t + dec_t).replace(0, np.nan)).fillna(0.5)
        ema10 = ratio.ewm(span=10, adjust=False).mean()
        zweig_ratio = float(ema10.iloc[-1])
        recent = ema10.iloc[-10:]
        thrust = bool(recent.min() < 0.40 and ema10.iloc[-1] > 0.615)

    return BreadthSnapshot(
        n_symbols=len(frames),
        advancers=advancers,
        decliners=decliners,
        net_advances=advancers - decliners,
        ad_ratio=round(ad_ratio, 3),
        uvol=uvol,
        dvol=dvol,
        vold=uvol - dvol,
        trin=round(trin, 3) if trin is not None else None,
        ad_line=[float(x) for x in ad_line.iloc[-60:]],
        mcclellan_osc=round(mcc_osc, 2) if mcc_osc is not None else None,
        mcclellan_sum=round(mcc_sum, 2) if mcc_sum is not None else None,
        pct_above_ma20=round(above20 / n20, 4) if n20 else None,
        pct_above_ma50=round(above50 / n50, 4) if n50 else None,
        pct_above_ma200=round(above200 / n200, 4) if n200 else None,
        net_new_highs=nh - nl,
        zweig_emaratio=round(zweig_ratio, 4) if zweig_ratio is not None else None,
        zweig_thrust=thrust,
    )


@dataclass
class PutCallRatio:
    volume_pc: float  # put volume / call volume
    oi_pc: float  # put OI / call OI
    call_volume: int
    put_volume: int


def put_call_ratio(chain: OptionChain) -> PutCallRatio | None:
    cv = sum(c.volume for c in chain.contracts if c.right == OptionRight.CALL)
    pv = sum(c.volume for c in chain.contracts if c.right == OptionRight.PUT)
    coi = sum(c.open_interest for c in chain.contracts if c.right == OptionRight.CALL)
    poi = sum(c.open_interest for c in chain.contracts if c.right == OptionRight.PUT)
    if cv + pv == 0:
        return None
    return PutCallRatio(
        volume_pc=round(pv / max(cv, 1), 3),
        oi_pc=round(poi / max(coi, 1), 3),
        call_volume=cv,
        put_volume=pv,
    )


@dataclass
class VolTermStructure:
    vix9d: float | None
    vix: float | None
    vix3m: float | None
    short_ratio: float | None  # VIX9D / VIX  (>1 = near-term stress)
    term_ratio: float | None  # VIX / VIX3M  (>1 = backwardation = fear)
    backwardation: bool


def vix_term_structure(aux: dict[str, OHLCV]) -> VolTermStructure | None:
    def last(sym):
        o = aux.get(sym)
        if o is None or len(o) == 0:
            return None
        return float(o.bars[-1].close)

    v9, v, v3 = last("^VIX9D"), last("^VIX"), last("^VIX3M")
    if v is None:
        return None
    short_ratio = round(v9 / v, 4) if v9 else None
    term_ratio = round(v / v3, 4) if v3 else None
    return VolTermStructure(
        vix9d=v9,
        vix=v,
        vix3m=v3,
        short_ratio=short_ratio,
        term_ratio=term_ratio,
        backwardation=bool(term_ratio and term_ratio > 1.0),
    )


def ratio_momentum(a: OHLCV | None, b: OHLCV | None, window: int = 20) -> float | None:
    """Relative-strength momentum of a/b over `window` bars (in %)."""
    if a is None or b is None or len(a) < window + 1 or len(b) < window + 1:
        return None
    fa, fb = ohlcv_to_frame(a)["close"], ohlcv_to_frame(b)["close"]
    joined = pd.concat([fa, fb], axis=1, keys=["a", "b"]).dropna()
    if len(joined) < window + 1:
        return None
    ratio = joined["a"] / joined["b"]
    return float(ratio.iloc[-1] / ratio.iloc[-window - 1] - 1.0)
