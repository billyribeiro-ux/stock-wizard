# Backtest Baselines

Baseline backtests of the price/structure scanners, run through the real `BacktestEngine`
(point-in-time windows, no lookahead) on **FMP split+dividend-adjusted daily data**.

- **Data:** FMP `historical-price-eod/dividend-adjusted`, ~3y (2023-06-26 → 2026-06-26).
- **Universe:** SPY, QQQ, AAPL, NVDA, TSLA, AMZN, META, JPM (8 liquid symbols).
- **Engine config:** $10k start, `min_score=0.35`, 1.0×ATR stop, 1.5/3.0×ATR targets,
  1bp slippage, 60-bar time stop, longs+shorts.
- **Caveat:** single ~3y window (a predominantly trending regime); these are baselines for
  relative scanner comparison and no-lookahead validation, not a deployment edge claim.
  Regime-segmented and walk-forward evaluation is the next step.

## Aggregate results (sum across the 8 symbols)

| Scanner | Trades | Win % | Net PnL (% of deployed capital) | Mean Sharpe |
|---|---:|---:|---:|---:|
| **breakout_quality** | 331 | 51.1 | **+12.1%** | **+1.57** |
| volume_profile_poc | 1221 | 41.8 | +5.3% | +0.38 |
| mtf_structure | 363 | 40.5 | +0.9% | −0.38 |
| rvol_expansion | 182 | 40.1 | +0.2% | −0.24 |
| liquidity_sweep | 503 | 37.2 | −4.8% | −0.39 |
| failed_move | 621 | 36.1 | −7.5% | −0.80 |
| key_levels | 1120 | 36.4 | −11.9% | −1.10 |
| momentum_ignition | 7 | 28.6 | −0.3% | (too few trades) |
| trend_exhaustion | 0 | — | — | did not trigger |
| squeeze_compression | 0 | — | — | did not trigger |

## Read

- **`breakout_quality` is the standout** — 51% win rate, PF up to 2.56 (JPM), mean Sharpe
  +1.57, positive on 7 of 8 symbols. Breakout/momentum logic shining over a trending
  window is expected and consistent.
- **`volume_profile_poc`** is broadly positive but trades a lot (high exposure) — net edge
  is thin per trade.
- **Mean-reversion-flavoured scanners (`key_levels`, `failed_move`, `liquidity_sweep`)**
  are net negative over this trending period — also as expected; they should be evaluated
  in range/chop regimes.
- **`trend_exhaustion` and `squeeze_compression` fired 0 trades** at `min_score=0.35` —
  flagged as a follow-up (threshold/condition review).
- Results are realistically mixed (no scanner shows implausible Sharpe on real data),
  which is the signature of a clean, no-lookahead backtest.

## Reproduce

The harness lives in the scratchpad (not committed; it's a throwaway). Set `FMP_KEY` and
point it at the basket above; it pulls adjusted daily bars and runs each scanner per
symbol. A committed regression fixture under `tests/backtest_regression/` is the next step
(see `TODO.md`).
