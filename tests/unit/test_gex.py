"""GEX profile, gamma walls, and gamma-flip golden tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from engine.features.gex import compute_gex_profile
from engine.schemas import OptionChain, OptionContract, OptionRight
from tests.conftest import make_chain

T = 0.5 / 252  # ~half a trading day


def test_symmetric_chain_total_gex_near_zero_and_flip_at_spot():
    now = datetime(2026, 6, 11, 15, 0, tzinfo=UTC)
    contracts = []
    for k in range(90, 111):
        for right in (OptionRight.CALL, OptionRight.PUT):
            contracts.append(
                OptionContract(
                    underlying="SPY",
                    expiry=date(2026, 6, 11),
                    strike=Decimal(k),
                    right=right,
                    bid=Decimal("1.0"),
                    ask=Decimal("1.1"),
                    open_interest=1000,
                    iv=0.2,
                    as_of=now,
                )
            )
    chain = OptionChain(underlying="SPY", as_of=now, spot=Decimal("100"), contracts=contracts)
    gp = compute_gex_profile(chain, t_years=T)
    assert gp is not None
    assert abs(gp.total_gex) < 1e-3
    assert gp.flip == pytest.approx(100.0, abs=1.0)


def test_walls_resolve_above_and_below_spot():
    chain = make_chain(spot=124.0, call_wall_offset=5, put_wall_offset=-5)
    gp = compute_gex_profile(chain, t_years=T)
    assert gp is not None
    assert gp.call_wall is not None and gp.call_wall >= 124.0
    assert gp.put_wall is not None and gp.put_wall < 124.0
    assert gp.call_wall == pytest.approx(129.0, abs=1.0)
    assert gp.put_wall == pytest.approx(119.0, abs=1.0)


def test_empty_chain_returns_none():
    now = datetime(2026, 6, 11, 15, 0, tzinfo=UTC)
    chain = OptionChain(underlying="SPY", as_of=now, spot=Decimal("100"), contracts=[])
    assert compute_gex_profile(chain, t_years=T) is None


def test_per_strike_net_consistency():
    chain = make_chain(spot=124.0)
    gp = compute_gex_profile(chain, t_years=T)
    total = sum(s.net for s in gp.per_strike)
    assert total == pytest.approx(gp.total_gex, rel=1e-9)
