"""Beyond-human math: Absorption Ratio (PCA), mutual information, purged walk-forward CV."""

from __future__ import annotations

import numpy as np

from engine.features import FeatureFactory
from engine.ml import (
    compute_absorption,
    mutual_information_ranking,
    purged_walk_forward_splits,
)
from engine.ml.cross_validation import purge_count
from engine.scanners import ScanContext, build_scanner
from engine.schemas import Timeframe
from tests.conftest import make_ohlcv


# ---------- Absorption Ratio (Kritzman-Lo) ----------
def _coupled_universe(n=200, k=12, rho=0.95):
    """Build a tightly-coupled basket: every name = common factor + small idiosyncratic."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from engine.schemas import OHLCV, MarketBar

    rng = np.random.default_rng(0)
    factor = np.cumsum(rng.normal(0, 1, n))
    base = datetime(2026, 1, 1, tzinfo=UTC)
    out = {}
    for j in range(k):
        idio = np.cumsum(rng.normal(0, 1 - rho, n))
        series = 100 + rho * factor + idio
        bars = []
        for i in range(n):
            px = float(series[i]) + 50
            bars.append(
                MarketBar(
                    symbol=f"C{j}",
                    timeframe=Timeframe.D1,
                    ts=base + timedelta(days=i),
                    open=Decimal(str(round(px, 2))),
                    high=Decimal(str(round(px + 0.5, 2))),
                    low=Decimal(str(round(px - 0.5, 2))),
                    close=Decimal(str(round(px, 2))),
                    volume=1_000_000,
                )
            )
        out[f"C{j}"] = OHLCV(symbol=f"C{j}", timeframe=Timeframe.D1, bars=bars)
    return out


def _independent_universe(n=200, k=12):
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from engine.schemas import OHLCV, MarketBar

    rng = np.random.default_rng(1)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    out = {}
    for j in range(k):
        series = 100 + np.cumsum(rng.normal(0, 1, n))
        bars = []
        for i in range(n):
            px = float(series[i]) + 50
            bars.append(
                MarketBar(
                    symbol=f"I{j}",
                    timeframe=Timeframe.D1,
                    ts=base + timedelta(days=i),
                    open=Decimal(str(round(px, 2))),
                    high=Decimal(str(round(px + 0.5, 2))),
                    low=Decimal(str(round(px - 0.5, 2))),
                    close=Decimal(str(round(px, 2))),
                    volume=1_000_000,
                )
            )
        out[f"I{j}"] = OHLCV(symbol=f"I{j}", timeframe=Timeframe.D1, bars=bars)
    return out


def test_absorption_higher_for_coupled_market():
    coupled = compute_absorption(_coupled_universe(), window=60)
    independent = compute_absorption(_independent_universe(), window=60)
    assert coupled is not None and independent is not None
    # a tightly-coupled market concentrates variance in fewer components
    assert coupled.absorption_ratio > independent.absorption_ratio
    assert 0 < coupled.absorption_ratio <= 1


def test_absorption_insufficient_universe():
    assert compute_absorption({"A": make_ohlcv(n=80)}) is None


def test_absorption_scanner_runs():
    ohlcv = make_ohlcv(n=120)
    ctx = ScanContext(
        symbol="SPY",
        timeframe=Timeframe.D1,
        snapshot=FeatureFactory().build_snapshot(ohlcv),
        ohlcv=ohlcv,
        aux=_coupled_universe(),
    )
    res = build_scanner("absorption_ratio").run(ctx)
    assert res.scanner_id == "absorption_ratio"
    assert "absorption_ratio" in res.feature_refs


# ---------- Mutual information ----------
def test_mutual_information_ranking():
    report = mutual_information_ranking(make_ohlcv(n=500, drift=0.05, amp=2.0), horizon=10)
    assert report is not None
    assert 0 <= report.label_entropy <= 1.0001
    assert len(report.rankings) > 0
    # rankings sorted descending by MI
    mis = [r.mutual_information for r in report.rankings]
    assert mis == sorted(mis, reverse=True)
    assert all(r.mutual_information >= 0 for r in report.rankings)


# ---------- Purged walk-forward CV ----------
def test_purged_walk_forward_no_overlap():
    horizon = 10
    folds = list(purged_walk_forward_splits(300, horizon=horizon, n_splits=5))
    assert len(folds) >= 4
    for train_idx, test_idx in folds:
        ts = min(test_idx)
        # no training sample's label window [i, i+horizon] may reach the test block
        assert max(train_idx) < ts - horizon + 1 or max(train_idx) <= ts - horizon
        assert set(train_idx).isdisjoint(test_idx)


def test_purge_count_positive():
    assert purge_count(300, horizon=10, n_splits=5) > 0


def test_model_report_has_cv_fields():
    from engine.ml import train_setup_model

    rep = train_setup_model(make_ohlcv(n=600, drift=0.05, amp=2.0), horizon=10)
    assert rep is not None
    assert rep.cv_folds >= 0
    assert 0.0 <= rep.cv_mean_accuracy <= 1.0
    assert 0.0 <= rep.cv_mean_auc <= 1.0
