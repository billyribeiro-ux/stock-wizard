"""Golden tests pinning the Black-Scholes greeks and IV solver."""

from __future__ import annotations

import math

import pytest
from scipy.stats import norm

from engine.features import greeks

S, K, T, R, SIG = 100.0, 100.0, 30 / 365, 0.05, 0.20


def test_gamma_matches_closed_form():
    d1 = (math.log(S / K) + (R + 0.5 * SIG**2) * T) / (SIG * math.sqrt(T))
    expected = norm.pdf(d1) / (S * SIG * math.sqrt(T))
    assert float(greeks.gamma(S, K, T, R, SIG)) == pytest.approx(expected, rel=1e-12)


def test_gamma_atm_known_value():
    # Pinned reference value for the ATM case above.
    assert float(greeks.gamma(S, K, T, R, SIG)) == pytest.approx(0.069228, abs=1e-6)


def test_put_call_delta_parity():
    dc = float(greeks.delta(S, K, T, R, SIG, "C"))
    dp = float(greeks.delta(S, K, T, R, SIG, "P"))
    assert dc - dp == pytest.approx(1.0, abs=1e-12)


def test_implied_vol_round_trip():
    price = float(greeks.bs_price(S, K, T, R, 0.27, "C"))
    iv = greeks.implied_vol(price, S, K, T, R, "C")
    assert iv == pytest.approx(0.27, abs=1e-3)


def test_implied_vol_rejects_subintrinsic():
    # Call worth less than intrinsic is impossible -> None.
    assert greeks.implied_vol(0.01, 120.0, 100.0, T, R, "C") is None


def test_gamma_handles_t_to_zero():
    # 0DTE near close: T floored, no blow-up / NaN.
    g = float(greeks.gamma(S, K, 0.0, R, SIG))
    assert math.isfinite(g) and g >= 0.0


def test_vega_positive():
    assert float(greeks.vega(S, K, T, R, SIG)) > 0
