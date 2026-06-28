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

## Walk-forward / out-of-sample validation

The in-sample table above is only the first gate. Each scanner was then run through
`backtesting/walkforward.py`: a 60/40 in-sample→out-of-sample split per symbol, with a
bootstrap Monte-Carlo on the OOS trades and a `promote / keep_testing / retire` decision
(`PF ≥ 1.3`, positive expectancy, win ≥ 40%, ≥ 5 trades), over ~5y of FMP daily data.

| Scanner | promote | keep | retire | mean OOS PF | Verdict |
|---|---:|---:|---:|---:|---|
| **breakout_quality** | 5 | 2 | 1 | **1.44** | Robust — survives OOS on most names |
| volume_profile_poc | 1 | 4 | 3 | 1.11 | Marginal — IS edge mostly fades OOS |
| mtf_structure | 2 | 1 | 5 | 0.93 | Largely overfit — IS PF collapses OOS |
| trend_exhaustion | 0 | 2 | 6 | 0.79 | No standalone edge (fading a bull trend) |

- **`breakout_quality` is the only scanner with broadly robust out-of-sample edge** —
  QQQ/AAPL/NVDA/TSLA/JPM all PROMOTE with Monte-Carlo p(profit) 83–95%. SPY/META sit at
  keep_testing; only AMZN retires.
- The others show the classic in-sample → out-of-sample decay: positive IS profit factors
  that don't survive on unseen data. This is the system working as intended (the blueprint's
  "nothing is trusted until it survives time-separated validation").
- `trend_exhaustion` now trades and is properly evaluated after the VWAP-distance fix
  below; as a standalone counter-trend fade it has no edge over this trending window, which
  is expected — its value is as a confluence input, not a standalone signal.

### Fix surfaced by these backtests
`trend_exhaustion` and several other daily scanners read `vwap.dist_atr`, which was built
from **session** VWAP — and session VWAP collapses to the bar's own typical price on
daily/weekly bars (one bar per calendar day), so the distance was always ~0 and
`trend_exhaustion` never triggered. `features/vwap.py` now uses session VWAP for intraday
data and a **rolling VWAP** for daily+ data, so the overextension signal is meaningful on
every timeframe. (`squeeze_compression` correctly stays at 0 trades — it is a directionless
watchlist signal; its directional companion is `momentum_ignition`.)

## Regime-segmented results (trend vs range)

The engine now tags every trade with the market regime at entry — `trend` vs `range`, via a
Kaufman **Efficiency Ratio** classifier (`features/regime.py`, point-in-time) — and emits a
per-regime `regime_breakdown` on every `BacktestResult`. Aggregated over the 8-symbol basket
(~3y daily):

| Scanner | range (trades / win% / PnL) | trend (trades / win% / PnL) | Read |
|---|---|---|---|
| **breakout_quality** | 128 / 52.3 / **+4107** | 203 / 50.2 / **+5555** | Edge in **both** regimes — genuinely robust |
| volume_profile_poc | 780 / 41.9 / +3180 | 441 / 41.5 / +1076 | Positive both; stronger in range (mean-reversion) |
| mtf_structure | 142 / 38.0 / **−674** | 221 / 42.1 / **+1359** | **Regime-dependent — only works in trend** |
| key_levels | 739 / 38.6 / −2793 | 381 / 32.3 / −6691 | Loses in both; far worse in trend |
| failed_move | 395 / 38.2 / −1849 | 226 / 32.3 / −4175 | Counter-trend fade; crushed in trends |

Actionable takeaways:

- **`breakout_quality` carries edge in both regimes** — the strongest evidence yet that it is
  a real signal, not a regime artifact.
- **`mtf_structure` is the textbook case for regime-gating**: net negative in range, clearly
  positive in trend. It should only be permitted (or weighted up) when the regime is `trend`.
- The mean-reversion-flavoured scanners (`key_levels`, `failed_move`) are worst in trends —
  fading a strong trend gets run over — confirming they belong to range regimes (and need
  better filters before they're tradeable at all).

## Feeding validation back into the ensemble

The walk-forward verdicts now flow into the edge-weighted consensus
(`evidence/ensemble.py`): `edge_weight_from_walkforward(promotion, oos_profit_factor)` maps a
scanner's out-of-sample result to its vote multiplier — `promote` scales with the validated
OOS profit factor (1.0–2.5), `keep_testing` stays neutral (1.0), and `retire` is damped to
0.3. So in a multi-scanner signal, `breakout_quality` (promoted, OOS PF ~1.44) out-votes an
overfit scanner like `mtf_structure` (retired) of equal raw score — proven scanners carry
proportionally more weight, exactly as the blueprint requires.

## Roster validation — blended out-of-sample edge per scanner

The batch roster pass (`POST /backtests/validate-roster`) forward-tests every
OHLCV-backtestable scanner across the basket, pools each symbol's out-of-sample trades per
scanner (`blend_forward_tests`), and assigns one blended edge weight. A **minimum of 30
pooled OOS trades** is required before a promote/retire verdict is allowed — below that the
scanner stays neutral (×1.0), because a scanner that "wins" 5 of 5 OOS trades is luck, not a
validated edge. (Run: 4 symbols — SPY/QQQ/NVDA/JPM — ~3y; `anomaly_detection` is excluded as
it re-fits a model every bar.)

| Edge | Scanner | Verdict | OOS trades | Note |
|---:|---|---|---:|---|
| **×1.50** | bigger_move | promote | 33 | z-score continuation — survives OOS |
| ×1.00 | breakout_quality | keep_testing | 61 | PF 1.25 OOS; promoted on the larger 8-sym/5y run |
| ×1.00 | long_trap | keep_testing | 100 | borderline (PF ~1.0) |
| ×1.00 | regime_classification | keep_testing | 193 | borderline (PF ~1.05) |
| ×1.00 | short_trap / reversal_master / momentum_ignition / volume_divergence / rvol_expansion | keep_testing | 1–15 | **below the 30-trade floor — neutral, not trusted** |
| **×0.30** | mtf_structure, key_levels, gap_scan, failed_move, liquidity_sweep, low_volume_pullback, pullback_classifier, seasonality, trend_exhaustion, volume_dryup_reversal, volume_profile_poc, anchored_vwap | retire | 40–216 | net-negative OOS over this trending window → damped |

Takeaways:

- The minimum-trade floor is what keeps this honest: without it, `short_trap` (6 trades,
  PF 7.5) and `reversal_master` (1 trade, PF 150) would have earned ×2.5 weights off pure
  noise. They're now correctly neutral until they accumulate enough OOS evidence.
- Only `bigger_move` earns a boost on this basket; most mean-reversion scanners retire OOS
  (consistent with the regime-segmented findings — they get run over in trends). The live
  ensemble now damps the retired set to ×0.30, so they barely vote.
- These weights are persisted (`model_registry`) and applied live by `scan_service`; re-run
  the endpoint on a larger basket / longer history to tighten the borderline calls.

## Evidence-driven trade-management study

Rather than tune by intuition, each proposed improvement was tested out-of-sample (forward
test across the basket) and adopted only if the evidence supported it. Two intuitive tweaks
were **rejected by the data**; one structural change was **kept**.

### Diagnostic (MFE/MAE per trade)
Across `breakout_quality` / `bigger_move` / `volume_profile_poc`: 58–68% of losers first
reached >0.5% profit (avg peak +1.0–1.4%) before reversing, and winners gave back ~1.2–1.8%
from their peak. This *suggested* a breakeven + trailing stop.

### Rejected: ratcheting stops (breakeven / trailing)
Implemented as no-lookahead config (`breakeven_atr`, `trail_atr`) and measured OOS:

| Policy | breakout_quality OOS PnL | win% | bigger_move OOS PnL |
|---|---:|---:|---:|
| baseline (fixed 1.0 ATR stop, 1.5/3.0 targets) | **+3966** | **55** | **+234** |
| breakeven @1.0 ATR | +2794 | 45 | −16 |
| breakeven + trail @2.0 | +2794 | 45 | −16 |
| breakeven 0.75 + trail 1.5 | +2279 | 39 | −66 |

The breakeven stop scratches more eventual winners (which dip to entry before running) than it
rescues losers — win rate falls 55%→45%. **Kept the capability, but default-OFF.** The fixed
exit policy is already near-optimal; shipping the "obvious" improvement would have degraded it.

### Rejected (mostly): conviction filtering (`min_score` sweep)
Raising the score threshold does **not** help the already-selective scanners
(`breakout_quality` best at 0.35–0.45, PF 1.85; degrades to 1.69 at 0.65). It helps only the
low-edge, high-frequency `volume_profile_poc` (PF 0.99→1.10 at 0.55) — but that scanner is
already OOS-retired and handled by the edge gate below, so no fragile per-scanner threshold is
hardcoded.

### Adopted: live edge gate (retire OOS-losers from trading)
The one change the evidence decisively supports. A scanner whose **validated OOS edge weight
marks it retired** (profit factor < 1 on time-separated data, weight 0.3) no longer produces a
tradeable signal: `build_signal` suppresses its plan (`_EDGE_FLOOR = 0.5`) and flags it
`edge-gated`, while still logging it for audit. Unproven scanners (weight 1.0) and promoted
ones (>1) trade normally — innocent until proven losing. This directly raises live expectancy
by not trading the scanners proven to lose, and composes with the regime gate.

### Multi-scanner ensemble (`backtest_ensemble`)
Fuses several scanners on the same bar via the edge-weighted consensus, dropping OOS-retired
scanners (edge weight < 0.5) before voting. Held-out 40%, 6-symbol basket:

| Strategy | trades | win% | meanPF | totPnL |
|---|---:|---:|---:|---:|
| breakout_quality alone | 149 | 49.7 | **1.47** | +3541 |
| bigger_move alone | 90 | 42.2 | 1.07 | +308 |
| ensemble (bq+bm, edge-weighted) | 229 | 47.2 | 1.32 | **+3879** |

The ensemble wins on **absolute** PnL (+10%) by capturing both scanners' opportunities, but
breakout_quality alone is better **risk-adjusted** (PF 1.47 vs 1.32) — naive fusion of
correlated edges adds turnover, not per-trade quality. So the ensemble is kept as a
*generalizing capability* (it auto-fuses validated edges and excludes retired ones as the
roster grows) rather than presented as a strict improvement over concentrating on the single
best edge. As more *independent* edges get validated, the consensus should improve risk-
adjusted returns; with two correlated momentum scanners today, it doesn't.

## Reproduce

The harness lives in the scratchpad (not committed; it's a throwaway). Set `FMP_KEY` and
point it at the basket above; it pulls adjusted daily bars and runs each scanner per
symbol. A committed regression fixture under `tests/backtest_regression/` is the next step
(see `TODO.md`).
