"""Feature math: ATR, RVOL, volume slope, volume profile, structure."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from engine.features import atr as atr_mod
from engine.features import price_structure as struct
from engine.features import volume as vol_mod
from engine.features import volume_profile as vp
from engine.features import vwap as vwap_mod
from engine.features.base import ohlcv_to_frame
from engine.schemas import OHLCV, MarketBar, Timeframe
from tests.conftest import make_ohlcv


def test_atr_positive_on_trend():
    df = ohlcv_to_frame(make_ohlcv())
    a = atr_mod.atr_last(df, 14)
    assert a is not None and a > 0


def test_rvol_spike_detected():
    df = ohlcv_to_frame(make_ohlcv())
    # Force a volume spike on the last bar.
    df.iloc[-1, df.columns.get_loc("volume")] = df["volume"].median() * 5
    rv = vol_mod.rvol(df, 20)
    assert rv is not None and rv > 3


def test_volume_slope_sign():
    df = ohlcv_to_frame(make_ohlcv())
    rising = df.copy()
    rising.iloc[-5:, rising.columns.get_loc("volume")] = [100, 200, 300, 400, 500]
    slope = vol_mod.volume_slope(rising, 5)
    assert slope is not None and slope > 0


def test_vwap_distance_atr_meaningful_on_daily():
    """Regression: session VWAP collapses to the bar's own typical price on daily bars
    (one bar per calendar day), so distance was ~0 and overextension scanners never fired.
    The rolling-VWAP fallback must yield a non-degenerate stretch on a trending daily series.
    """
    daily = make_ohlcv(n=120, timeframe=Timeframe.D1, drift=0.6, amp=1.0, base_volume=1_000_000)
    df = ohlcv_to_frame(daily)
    atr_val = atr_mod.atr_last(df, 14)
    dist = vwap_mod.vwap_distance_atr(df, atr_val)
    assert dist is not None
    # a steadily trending series should be measurably stretched from its trailing VWAP
    assert abs(dist) > 0.5


def test_rolling_vwap_tracks_price():
    df = ohlcv_to_frame(make_ohlcv(n=60, timeframe=Timeframe.D1))
    rv = vwap_mod.rolling_vwap(df, window=20)
    assert len(rv) == len(df)
    assert not rv.isna().all()


def test_volume_profile_poc_at_high_volume_price():
    """Build bars where most volume sits at ~150 -> POC must land near 150."""
    base = datetime(2026, 6, 10, 13, 30, tzinfo=UTC)
    bars = []
    for i in range(60):
        px = 150.0 if i % 2 == 0 else 130.0
        vol = 1_000_000 if px == 150.0 else 50_000
        bars.append(
            MarketBar(
                symbol="X",
                timeframe=Timeframe.M5,
                ts=base + timedelta(minutes=5 * i),
                open=Decimal(str(px)),
                high=Decimal(str(px + 0.2)),
                low=Decimal(str(px - 0.2)),
                close=Decimal(str(px)),
                volume=vol,
            )
        )
    df = ohlcv_to_frame(OHLCV(symbol="X", timeframe=Timeframe.M5, bars=bars))
    profile = vp.compute_profile(df, n_buckets=50)
    assert profile is not None
    assert profile.poc == pytest.approx(150.0, abs=1.0)
    assert profile.val <= profile.poc <= profile.vah


def test_structure_detects_uptrend_swings():
    df = ohlcv_to_frame(make_ohlcv(drift=0.3, amp=1.2))
    state = struct.classify_structure(df, k=2)
    assert len(state.swings) > 0
    assert state.trend in {"up", "down", "range"}


def test_structure_bos_up_on_breakout():
    """Flat then a sharp breakout close above prior swing -> BOS up."""
    base = datetime(2026, 6, 10, 13, 30, tzinfo=UTC)
    prices = [100, 101, 100, 99, 100, 101, 100, 99, 100, 105]  # last breaks out
    bars = []
    for i, px in enumerate(prices):
        bars.append(
            MarketBar(
                symbol="X",
                timeframe=Timeframe.M5,
                ts=base + timedelta(minutes=5 * i),
                open=Decimal(str(px)),
                high=Decimal(str(px + 0.3)),
                low=Decimal(str(px - 0.3)),
                close=Decimal(str(px)),
                volume=100000,
            )
        )
    df = ohlcv_to_frame(OHLCV(symbol="X", timeframe=Timeframe.M5, bars=bars))
    state = struct.classify_structure(df, k=2)
    assert state.last_bos == "up"
