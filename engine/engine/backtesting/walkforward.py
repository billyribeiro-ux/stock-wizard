"""Walk-forward validation, Monte-Carlo stress, and forward (paper) testing.

The blueprint's precision standard: nothing is trusted until it survives time-separated
validation and forward testing. These tools split history into in-sample vs out-of-sample
periods, measure drift, bootstrap the trade sequence, and emit a promotion decision.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

from ..schemas import OHLCV, BacktestResult, MarketBar
from .engine import BacktestConfig, BacktestEngine


def _slice(ohlcv: OHLCV, lo: int, hi: int) -> OHLCV:
    return OHLCV(
        symbol=ohlcv.symbol,
        timeframe=ohlcv.timeframe,
        asset_class=ohlcv.asset_class,
        source=ohlcv.source,
        bars=ohlcv.bars[lo:hi],
    )


def _htf_upto(htf: OHLCV | None, ts) -> OHLCV | None:
    if htf is None:
        return None
    bars = [b for b in htf.bars if b.ts <= ts]
    return (
        OHLCV(symbol=htf.symbol, timeframe=htf.timeframe, source=htf.source, bars=bars)
        if bars
        else None
    )


@dataclass
class MonteCarlo:
    n_sims: int
    prob_profit: float
    median_return: float
    p05_return: float
    p95_return: float
    median_max_dd: float
    worst_max_dd: float


def monte_carlo(
    trades, starting_equity: float = 10_000.0, n_sims: int = 1000, seed: int = 42
) -> MonteCarlo | None:
    pnls = [float(t.pnl) for t in trades if t.pnl is not None]
    if len(pnls) < 5:
        return None
    rng = random.Random(seed)
    finals, dds = [], []
    for _ in range(n_sims):
        seq = [rng.choice(pnls) for _ in pnls]  # bootstrap resample
        eq = starting_equity
        peak = eq
        mdd = 0.0
        for p in seq:
            eq += p
            peak = max(peak, eq)
            if peak > 0:
                mdd = max(mdd, (peak - eq) / peak)
        finals.append((eq - starting_equity) / starting_equity)
        dds.append(mdd)
    finals.sort()
    dds.sort()

    def pct(arr, q):
        return arr[min(len(arr) - 1, int(q * len(arr)))]

    return MonteCarlo(
        n_sims=n_sims,
        prob_profit=round(sum(1 for f in finals if f > 0) / len(finals), 4),
        median_return=round(pct(finals, 0.5), 4),
        p05_return=round(pct(finals, 0.05), 4),
        p95_return=round(pct(finals, 0.95), 4),
        median_max_dd=round(pct(dds, 0.5), 4),
        worst_max_dd=round(pct(dds, 0.95), 4),
    )


@dataclass
class ForwardTest:
    scanner_id: str
    baseline: dict  # in-sample metrics
    forward: dict  # out-of-sample metrics
    drift: dict  # forward - baseline on key metrics
    monte_carlo: dict | None
    promotion: str  # promote | keep_testing | retire
    rationale: str
    out_of_sample: BacktestResult = field(default=None)  # type: ignore


def _decide(baseline: dict, forward: dict) -> tuple[str, str]:
    fpf = forward.get("profit_factor", 0)
    fexp = forward.get("expectancy", 0)
    fwin = forward.get("win_rate", 0)
    ftrades = forward.get("total_trades", 0)
    if ftrades < 5:
        return "keep_testing", "Too few out-of-sample trades to judge."
    if fexp <= 0 or fpf < 1.0:
        return "retire", f"Out-of-sample expectancy {fexp} / PF {fpf} is unprofitable."
    if fpf >= 1.3 and fexp > 0 and fwin >= 0.4:
        return "promote", f"Out-of-sample PF {fpf}, win rate {fwin:.0%}, positive expectancy."
    return "keep_testing", f"Out-of-sample PF {fpf} is positive but not yet convincing."


def forward_test(
    scanner_id: str,
    ohlcv: OHLCV,
    params: dict | None = None,
    htf_ohlcv: OHLCV | None = None,
    split_frac: float = 0.6,
    config: BacktestConfig | None = None,
) -> ForwardTest | None:
    bars: list[MarketBar] = ohlcv.bars
    if len(bars) < 200:
        return None
    split = int(len(bars) * split_frac)
    in_sample = _slice(ohlcv, 0, split)
    out_sample = _slice(ohlcv, split, len(bars))
    split_ts = bars[split].ts

    engine = BacktestEngine(config)
    base_res = engine.run(
        scanner_id, in_sample, params=params, htf_ohlcv=_htf_upto(htf_ohlcv, split_ts)
    )
    fwd_res = engine.run(scanner_id, out_sample, params=params, htf_ohlcv=htf_ohlcv)

    base_m = base_res.metrics.model_dump(mode="json")
    fwd_m = fwd_res.metrics.model_dump(mode="json")
    drift = {
        k: round(float(fwd_m.get(k, 0)) - float(base_m.get(k, 0)), 4)
        for k in ("win_rate", "profit_factor", "expectancy", "sharpe", "max_drawdown")
    }
    mc = monte_carlo(fwd_res.trades)
    promotion, rationale = _decide(base_m, fwd_m)
    return ForwardTest(
        scanner_id=scanner_id,
        baseline=base_m,
        forward=fwd_m,
        drift=drift,
        monte_carlo=asdict(mc) if mc else None,
        promotion=promotion,
        rationale=rationale,
        out_of_sample=fwd_res,
    )


def walk_forward(
    scanner_id: str,
    ohlcv: OHLCV,
    params: dict | None = None,
    htf_ohlcv: OHLCV | None = None,
    n_splits: int = 4,
    config: BacktestConfig | None = None,
) -> list[dict]:
    """Rolling anchored walk-forward: expand the train window, test the next slice."""
    bars = ohlcv.bars
    if len(bars) < 250:
        return []
    engine = BacktestEngine(config)
    step = len(bars) // (n_splits + 1)
    out: list[dict] = []
    for i in range(1, n_splits + 1):
        test_lo, test_hi = i * step, (i + 1) * step
        test = _slice(ohlcv, test_lo, min(test_hi, len(bars)))
        res = engine.run(
            scanner_id, test, params=params, htf_ohlcv=_htf_upto(htf_ohlcv, bars[test_lo].ts)
        )
        out.append(
            {
                "split": i,
                "period_start": res.period_start.isoformat(),
                "period_end": res.period_end.isoformat(),
                "metrics": res.metrics.model_dump(mode="json"),
            }
        )
    return out
