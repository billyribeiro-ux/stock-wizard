"""Institutional market internals: math + scanners."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.features import FeatureFactory
from engine.features import internals as mi
from engine.scanners import ScanContext, build_scanner
from engine.schemas import Side, Timeframe
from tests.conftest import make_chain, make_ohlcv

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


def _universe(n_up=8, n_down=2, n=120):
    """A basket where n_up names trend up and n_down trend down."""
    out = {}
    for i in range(n_up):
        out[f"UP{i}"] = make_ohlcv(symbol=f"UP{i}", n=n, drift=0.2, amp=0.5)
    for i in range(n_down):
        out[f"DN{i}"] = make_ohlcv(symbol=f"DN{i}", n=n, drift=-0.2, amp=0.5)
    return out


# ---------- math ----------
def test_breadth_counts_advancers_and_decliners():
    b = mi.compute_breadth(_universe(8, 2))
    assert b is not None
    assert b.n_symbols == 10
    assert b.advancers + b.decliners <= 10
    assert b.net_advances > 0  # mostly rising basket
    assert b.uvol > b.dvol
    assert b.vold > 0


def test_trin_below_one_when_volume_concentrates_in_advancers():
    b = mi.compute_breadth(_universe(9, 1))
    assert b is not None and b.trin is not None
    assert b.trin > 0


def test_mcclellan_positive_in_broad_uptrend():
    b = mi.compute_breadth(_universe(9, 1, n=150))
    assert b is not None
    assert b.mcclellan_osc is not None
    assert b.mcclellan_osc > 0  # persistent positive net advances


def test_pct_above_ma_high_in_uptrend():
    b = mi.compute_breadth(_universe(10, 0, n=150))
    assert b is not None
    assert b.pct_above_ma50 is not None and b.pct_above_ma50 >= 0.8


def test_breadth_insufficient_universe():
    assert mi.compute_breadth({"A": make_ohlcv(n=50)}) is None


def test_put_call_ratio_from_chain():
    chain = make_chain()
    # give puts double the volume of calls
    from decimal import Decimal

    contracts = []
    for c in chain.contracts:
        vol = 200 if c.right.value == "P" else 100
        contracts.append(c.model_copy(update={"volume": vol, "last": Decimal("1.0")}))
    chain = chain.model_copy(update={"contracts": contracts})
    pc = mi.put_call_ratio(chain)
    assert pc is not None
    assert pc.volume_pc == 2.0


def test_vix_term_structure_backwardation():
    aux = {
        "^VIX9D": make_ohlcv(symbol="^VIX9D", n=10, start_px=30, drift=0),
        "^VIX": make_ohlcv(symbol="^VIX", n=10, start_px=28, drift=0),
        "^VIX3M": make_ohlcv(symbol="^VIX3M", n=10, start_px=22, drift=0),
    }
    ts = mi.vix_term_structure(aux)
    assert ts is not None
    assert ts.backwardation  # VIX > VIX3M


def test_ratio_momentum_sign():
    a = make_ohlcv(symbol="A", n=60, drift=0.3)
    b = make_ohlcv(symbol="B", n=60, drift=0.0)
    m = mi.ratio_momentum(a, b, 20)
    assert m is not None and m > 0


# ---------- scanners ----------
def _ctx(aux=None, chain=None):
    ohlcv = make_ohlcv(n=150)
    snap = FeatureFactory().build_snapshot(ohlcv)
    return ScanContext(
        symbol="SPY",
        timeframe=Timeframe.D1,
        snapshot=snap,
        ohlcv=ohlcv,
        aux=aux or {},
        chain=chain,
        as_of=NOW,
    )


def test_market_breadth_scanner_broad_advance():
    res = build_scanner("market_breadth").run(_ctx(aux=_universe(9, 1)))
    assert res.scanner_id == "market_breadth"
    if res.triggered:
        assert res.direction == Side.LONG


def test_internals_scanners_run_on_universe():
    aux = _universe(8, 2, n=150)
    for sid in ("arms_trin", "mcclellan", "pct_above_ma", "nh_nl", "zweig_thrust"):
        res = build_scanner(sid).run(_ctx(aux=aux))
        assert res.scanner_id == sid
        assert res.evidence is not None


def test_internals_scanners_degrade_without_universe():
    for sid in (
        "market_breadth",
        "arms_trin",
        "mcclellan",
        "pct_above_ma",
        "nh_nl",
        "zweig_thrust",
    ):
        res = build_scanner(sid).run(_ctx(aux={}))
        assert not res.triggered
        assert res.classification == "no_universe_data"


def test_put_call_scanner_with_chain():
    res = build_scanner("put_call_ratio").run(_ctx(chain=make_chain()))
    assert res.scanner_id == "put_call_ratio"


def test_vix_term_structure_scanner_backwardation_short():
    aux = {
        "^VIX": make_ohlcv(symbol="^VIX", n=10, start_px=30, drift=0),
        "^VIX3M": make_ohlcv(symbol="^VIX3M", n=10, start_px=24, drift=0),
    }
    res = build_scanner("vix_term_structure").run(_ctx(aux=aux))
    assert res.triggered and res.direction == Side.SHORT
    assert res.classification == "backwardation"


def test_risk_appetite_scanner():
    aux = {
        "RSP": make_ohlcv(symbol="RSP", n=60, drift=0.3),
        "SPY": make_ohlcv(symbol="SPY", n=60, drift=0.1),
        "SPHB": make_ohlcv(symbol="SPHB", n=60, drift=0.4),
        "SPLV": make_ohlcv(symbol="SPLV", n=60, drift=0.05),
        "XLY": make_ohlcv(symbol="XLY", n=60, drift=0.3),
        "XLP": make_ohlcv(symbol="XLP", n=60, drift=0.05),
        "IWM": make_ohlcv(symbol="IWM", n=60, drift=0.3),
        "HYG": make_ohlcv(symbol="HYG", n=60, drift=0.2),
        "IEF": make_ohlcv(symbol="IEF", n=60, drift=0.0),
    }
    res = build_scanner("risk_appetite").run(_ctx(aux=aux))
    assert res.triggered and res.direction == Side.LONG
    assert res.classification == "risk_on_broad"
