# Changelog

All notable changes to **Stock Wizard** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project is pre-1.0 and versions track development waves rather than semver releases.

## [Unreleased]

### Added
- **Ensemble builder UI** (`/ensemble`) — multi-select scanners (each showing its global +
  per-regime edge badges), pick symbols/timeframe/history, dispatch a regime-conditional
  ensemble scan and land on the results. Added to the nav.
- **Live regime-conditional ensemble scan** (`POST /scans/ensemble` + `ensemble_service`) —
  the production form of the validated 2x strategy: per symbol it runs the chosen scanners on
  one snapshot, weights each by its *current-regime* OOS edge (persisted `regime_edges`),
  drops those with no proven edge in that regime, fuses the survivors via the edge-weighted
  consensus, and emits one ensemble `SignalPacket` (each contributor's result still saved for
  audit). Wired through the web client (`startEnsembleScan`/`runEnsembleScan`); covered by an
  end-to-end integration test on the real Postgres/Redis stack.
- **Regime-conditional edge weights (the key evidence win).** Reading each scanner's OOS
  performance *per regime* shows scanners that are globally net-flat but profitable in one
  regime — e.g. `volume_profile_poc` is real mean-reversion edge in *range* (OOS PF 1.19,
  +3369) yet a loser in trend, so the global gate wrongly retired it. `blend_forward_tests`
  now derives per-regime weights (`regime_edges`, persisted via `save_walkforward_edge`), and
  `build_signal` applies the weight for the *current* regime — so a scanner trades only where
  it's OOS-proven and is gated where it isn't. Resurrects range mean-reversion as an
  independent edge for the ensemble. See `docs/BACKTESTS.md`.
- **Regime-conditional ensemble** (`backtest_ensemble` + `regime_edges_map`) — fuses scanners
  on each bar weighting each by its edge in the *current* regime. Fusing momentum (trend) with
  range-only mean-reversion **more than doubles** the best single scanner's held-out profit
  (+7424 vs +3541, PF 1.30) — versus a naive correlated-momentum ensemble that barely beat it
  (+3879). Independence is the key: regime-gating makes the edges add, not dilute. See
  `docs/BACKTESTS.md`.
- **Evidence-driven trade management (measured, not guessed).** Added no-lookahead ratcheting
  stops (`breakeven_atr`/`trail_atr` in `BacktestConfig`) and tested them OOS — they *degrade*
  the proven scanners (breakout_quality +3966→+2794, win 55%→45%), so they're kept default-OFF.
  Conviction (`min_score`) sweeps likewise don't help the selective scanners. The one change
  the data supports: a **live edge gate** — `build_signal` suppresses the trade plan for any
  scanner whose validated OOS edge weight marks it *retired* (PF < 1; weight < 0.5), flagged
  `edge-gated` and logged for audit. Full study in `docs/BACKTESTS.md`.
- **End-to-end integration test against a real Postgres + Redis** (`tests/integration/
  test_e2e_pipeline.py`): drives the real FastAPI app + DB through health → encrypted vendor
  key → scan → execute → results/signals (carrying regime/edge) → forward backtest → persisted
  & served edge weight. Skips cleanly when infra is absent (unit-only envs stay green).
- **Scheduled roster re-validation.** New `run_roster_validation` worker task on a weekly arq
  cron (Sun 02:00 UTC) keeps each scanner's out-of-sample edge weight fresh.
- **Batch roster validation (system-wide self-grading).** `backtesting/roster.py`
  (`blend_forward_tests`) pools each symbol's out-of-sample trades per scanner into one
  blended promotion + edge weight; `services/roster_service.py` forward-tests the whole
  OHLCV-backtestable roster across a basket (on the FMP feed) and persists each scanner's
  blended edge weight. New endpoints `POST /backtests/validate-roster` and
  `GET /backtests/edge-weights`; the ML Lab gains a "Scanner edge weights" panel with a
  one-click roster-validate button. `scan_service` already prefers these persisted weights.
  A **30-trade minimum** floor keeps a scanner neutral until there's enough pooled OOS
  evidence (so a 6-trade PF-7 fluke can't earn a boost), and per-bar-fitting scanners
  (`anomaly_detection`) are excluded from the sweep.
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
- **Non-finite floats broke JSONB persistence.** A signal/result/backtest payload containing
  `inf`/`-inf`/`NaN` (e.g. a profit factor with zero losses) made Postgres reject the INSERT
  ("invalid input syntax for type json: Token 'Infinity'") and roll back the write. The repo
  now sanitizes all JSONB payloads (`_json_safe`) — caught by the new e2e test.
- **Migration assumed TimescaleDB.** `0001_initial` now probes `pg_available_extensions`
  first and creates plain tables when TimescaleDB is absent (dev/CI/test), so migrations run
  on a vanilla Postgres; hypertables are still created when the extension is present.
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
