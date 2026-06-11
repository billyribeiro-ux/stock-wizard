"""FeatureFactory — assembles a point-in-time FeatureSnapshot from OHLCV (+ chain).

Scalar evidence goes in ``features`` (namespaced); larger artifacts (volume-profile
buckets, per-strike GEX) go in ``meta`` for charts. The factory is the single place
the scanners get their inputs, so every scanner sees a consistent, versioned view.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from ..schemas import OHLCV, FeatureSnapshot, OptionChain, Regime
from . import atr as atr_mod
from . import gex as gex_mod
from . import price_structure as struct_mod
from . import volume as vol_mod
from . import volume_profile as vp_mod
from . import vwap as vwap_mod
from .base import ohlcv_to_frame

_TREND_CODE = {"up": 1.0, "down": -1.0, "range": 0.0}
_DIR_CODE = {"up": 1.0, "down": -1.0, None: 0.0}


def _time_to_expiry_years(as_of: datetime, expiry: date) -> float:
    """0DTE-aware time to expiry in years (floored to avoid greeks blow-ups)."""
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    days = (expiry - as_of.date()).days
    if days <= 0:
        # Same-day: fraction of a 6.5h session remaining, in trading-year units.
        from common.timeutils import year_fraction_to_close

        return year_fraction_to_close(as_of)
    return max(days / 365.0, 1e-6)


class FeatureFactory:
    def __init__(self, atr_period: int = 14, rvol_lookback: int = 20):
        self.atr_period = atr_period
        self.rvol_lookback = rvol_lookback

    def build_snapshot(
        self,
        ohlcv: OHLCV,
        chain: OptionChain | None = None,
        chain_expiry: date | None = None,
    ) -> FeatureSnapshot:
        df = ohlcv_to_frame(ohlcv)
        ts = ohlcv.bars[-1].ts if ohlcv.bars else datetime.now(UTC)
        feats: dict[str, float | None] = {}
        meta: dict = {}
        regime = Regime.UNKNOWN

        if not df.empty:
            close = float(df["close"].iloc[-1])
            feats["price.close"] = close

            a = atr_mod.atr_last(df, self.atr_period)
            feats["atr.14"] = a
            feats["rvol.20"] = vol_mod.rvol(df, self.rvol_lookback)
            feats["vol.slope5"] = vol_mod.volume_slope(df, 5)
            feats["vol.updown"] = vol_mod.up_down_volume_ratio(df, self.rvol_lookback)

            state = struct_mod.classify_structure(df)
            feats["struct.trend"] = _TREND_CODE.get(state.trend, 0.0)
            feats["struct.bos"] = _DIR_CODE.get(state.last_bos, 0.0)
            feats["struct.choch"] = _DIR_CODE.get(state.last_choch, 0.0)
            feats["struct.last_high"] = state.last_swing_high
            feats["struct.last_low"] = state.last_swing_low
            meta["swings"] = [
                {"ts": s.ts.isoformat(), "price": s.price, "kind": s.kind.value}
                for s in state.swings[-20:]
            ]
            if state.trend == "up":
                regime = Regime.TREND_UP
            elif state.trend == "down":
                regime = Regime.TREND_DOWN
            else:
                regime = Regime.RANGE

            feats["vwap.dist_atr"] = vwap_mod.vwap_distance_atr(df, a)

            profile = vp_mod.compute_profile(df)
            if profile is not None:
                feats["vp.poc"] = profile.poc
                feats["vp.vah"] = profile.vah
                feats["vp.val"] = profile.val
                meta["volume_profile"] = {
                    "centers": profile.bucket_centers,
                    "volume": profile.bucket_volume,
                    "poc": profile.poc,
                    "vah": profile.vah,
                    "val": profile.val,
                }

        if chain is not None:
            expiry = chain_expiry or (chain.expiries[0] if chain.expiries else None)
            if expiry is not None:
                t_years = _time_to_expiry_years(chain.as_of, expiry)
                gp = gex_mod.compute_gex_profile(chain, t_years, expiry)
                if gp is not None:
                    feats["gex.total"] = gp.total_gex
                    feats["gex.flip"] = gp.flip
                    feats["gex.call_wall"] = gp.call_wall
                    feats["gex.put_wall"] = gp.put_wall
                    feats["gex.regime"] = 1.0 if gp.regime == "positive" else -1.0
                    feats["gex.spot"] = gp.spot
                    feats["gex.degraded"] = 1.0 if gp.degraded else 0.0
                    meta["gex_profile"] = {
                        "spot": gp.spot,
                        "expiry": gp.expiry.isoformat(),
                        "flip": gp.flip,
                        "call_wall": gp.call_wall,
                        "put_wall": gp.put_wall,
                        "total_gex": gp.total_gex,
                        "regime": gp.regime,
                        "per_strike": [
                            {
                                "strike": s.strike,
                                "call_gex": s.call_gex,
                                "put_gex": s.put_gex,
                                "net": s.net,
                            }
                            for s in gp.per_strike
                        ],
                    }
                    regime = (
                        Regime.POSITIVE_GAMMA if gp.regime == "positive" else Regime.NEGATIVE_GAMMA
                    )

        return FeatureSnapshot(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            ts=ts,
            features=feats,
            meta=meta,
            regime=regime,
        )
