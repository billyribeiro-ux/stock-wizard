# Changelog

All notable changes to **Stock Wizard** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project is pre-1.0 and versions track development waves rather than semver releases.

## [Unreleased]

### Added
- **Persisted walk-forward edge weights, applied live.** A forward-test backtest now persists
  the out-of-sample verdict + derived edge weight per scanner
  (`repo.save_walkforward_edge` → `model_registry` as `walkforward:{scanner_id}`), and
  `scan_service` prefers that *time-separated* OOS weight over the calibrator-derived one when
  present. Backtests now run on the FMP-preferred data resolver (same as the live scan path).
- **Regime/edge surfaced in the dashboard.** `SignalCard` shows a "gated" badge when a signal
  was regime-suppressed and an edge-weight chip (×N, green/red) when a scanner's validated
  edge departs from neutral.
- **Live regime-gating + edge weighting in the signal path.** `build_signal` now demotes a
  triggered signal when its source scanner has no validated edge in the current regime
  (`scanners/regime_affinity.py`, derived from the regime-segmented backtests — e.g.
  `mtf_structure` is trend-only): the trade plan is suppressed, `regime_aligned=False` is
  set, and a note explains the gate. The snapshot now carries `regime.er` (Kaufman
  efficiency ratio, same classifier as the backtester). `SignalPacket` gains `regime_aligned`
  and `edge_weight`; `scan_service` populates `edge_weight` from the calibrated win-rate lift
  so proven scanners are surfaced as such. TS types + contract schema updated.
- **Regime-segmented backtesting.** New `features/regime.py` (Kaufman Efficiency Ratio →
  trend/range, point-in-time) and `BacktestEngine` now tags each trade with its entry regime
  and populates `BacktestResult.regime_breakdown` (per-regime metrics). Surfaced that
  `mtf_structure` only has edge in trend regimes, while `breakout_quality` works in both —
  see `docs/BACKTESTS.md`.
- **Walk-forward verdicts feed the ensemble.** `evidence/ensemble.py` gains
  `edge_weight_from_walkforward(promotion, oos_profit_factor)` — OOS-promoted scanners scale
  their consensus vote with their validated profit factor (1.0–2.5), `keep_testing` is
  neutral, `retire` is damped to 0.3. Proven scanners now carry proportionally more weight.
- **Charles Schwab data adapter** (`engine/data/schwab_source.py`) — OAuth2 (3-legged)
  equity OHLCV and real option chains with vendor greeks/OI/IV (preferred for the gamma
  engine). Includes `SchwabCreds` encrypted bundle, `SchwabAuth` (authorize URL, code
  exchange, token refresh) and server-side token lifecycle (`services/schwab_creds.py`,
  `repo.update_vendor_key_ciphertext`).
- **Schwab OAuth API endpoints** — `POST /vendors/schwab/connect` (store app key/secret,
  return authorize URL) and `POST /vendors/schwab/token` (exchange the pasted redirect
  code, enable the key).
- **Schwab Connect flow in Settings** — two-step progressively-enhanced forms so the app
  secret and tokens never enter the client bundle.
- `name: str` is now part of the data-source `Protocol`s (every adapter already set it).
- `CHANGELOG.md` and `TODO.md` for ongoing tracking.

### Changed
- **FMP adapter migrated to the FMP "stable" API.** The v3 `historical-price-full` /
  `profile` endpoints were retired for new keys on 2025-08-31 (they now return HTTP 403
  "Legacy Endpoint"). Daily now uses `historical-price-eod/dividend-adjusted` (split +
  dividend adjusted OHLC) and intraday uses `historical-chart/{interval}`, both keyed by
  `?symbol=&from=&to=`.

### Fixed
- **`vwap.dist_atr` was degenerate on daily+ bars.** It was built from *session* VWAP,
  which collapses to a single bar's typical price when there's one bar per calendar day, so
  the distance read ~0 and `trend_exhaustion` (plus other daily scanners reading it) never
  saw overextension. `features/vwap.py` now uses session VWAP intraday and a **rolling
  VWAP** on daily+ data. `trend_exhaustion` now triggers and is evaluated properly.
- **`.gitignore` was swallowing the entire data-adapter package.** The unanchored `data/`
  rule matched `engine/engine/data/`, so 11 source files (yfinance, EDGAR, Finnhub, FMP,
  Schwab, base protocols, registry, validation, calendar, internals stub) had never been
  committed. Anchored the rule to `/data/` and added the files.
- **Repo-wide type and lint cleanup** — mypy 54 → 0 across 19 files (Optional narrowing in
  scanners/features/backtesting, `__table__` casts in Alembic migrations, typed
  `enqueue_training` args, test-side narrowing); ruff check + format clean; web prettier +
  eslint + svelte-check all green.

### Verified
- **Baseline backtests on real FMP adjusted daily data** (8 liquid symbols, ~3y) across 10
  price/structure scanners — see `docs/BACKTESTS.md`. `breakout_quality` leads (+12.1% of
  deployed capital, mean Sharpe +1.57, 51% win rate); results are realistically mixed,
  confirming no-lookahead behaviour.
- **Walk-forward / out-of-sample validation** (60/40 split + Monte-Carlo + promote/retire
  decisions, ~5y): `breakout_quality` is the only broadly robust scanner OOS (5/8 PROMOTE,
  mean OOS PF 1.44, MC p(profit) 83–95%); the rest show in-sample→OOS decay, as expected.
- `pytest` 278 unit tests pass (added VWAP-distance regression tests); full lint/type/
  web-check suite clean.
