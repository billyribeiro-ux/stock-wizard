# TODO

Working tracker for active and near-term work. The exhaustive scanner/backtester/signal
checklist lives in [`docs/ROADMAP.md`](docs/ROADMAP.md); this file is the short list of
what's in flight and what's next.

## In progress
- [x] FMP adapter on the stable API (v3 endpoints retired 2025-08-31) — real adjusted
      daily + intraday OHLCV.
- [x] Charles Schwab OAuth2 adapter (OHLCV + real option chains with greeks).
- [x] Multi-vendor encrypted key management (add / rotate / rename / swap / delete) + UI.
- [x] Repo-wide lint/type cleanup (mypy 0, ruff/prettier/eslint/svelte-check clean).
- [x] Run real backtests on FMP data and capture a baseline → `docs/BACKTESTS.md`.
- [x] Make `main` the repository branch carrying all work + align development onto it.

## Next up
- [ ] Set `main` as the GitHub **default branch** (repo Settings → Branches — needs the UI
      or an admin API call; not exposed to the agent toolset).
- [x] Investigate `trend_exhaustion`/`squeeze_compression` zero-trade behaviour — fixed the
      session-VWAP-on-daily bug (`trend_exhaustion`); `squeeze_compression` is a
      directionless watchlist signal by design.
- [x] Walk-forward + out-of-sample validation across the basket → `docs/BACKTESTS.md`.
- [x] Regime-segmented backtests (trend vs range) → `BacktestResult.regime_breakdown` +
      `features/regime.py`; surfaced `mtf_structure` as trend-only.
- [x] Feed walk-forward OOS verdicts into the edge-weighted ensemble
      (`edge_weight_from_walkforward`).
- [x] Regime-**gate** trend-only scanners (e.g. `mtf_structure`) in the live signal path —
      `build_signal` suppresses the plan + flags `regime_aligned=False` in unfavourable
      regimes (`scanners/regime_affinity.py`, snapshot `regime.er`).
- [x] Surface per-scanner edge weight on signals (`SignalPacket.edge_weight`, from the
      calibrated win-rate lift via `scan_service`).
- [x] Persist *walk-forward OOS* edge weights per scanner (`model_registry`) and prefer them
      in `scan_service` over the calibrator-derived weight.
- [x] Surface the regime-gate badge + edge-weight chip in the signal UI (`SignalCard`).
- [x] Run backtests on the FMP-preferred data resolver (not hard-coded yfinance).
- [ ] Wire the FMP key into a Settings entry end-to-end and confirm a live scan uses it
      (needs a running DB; validated offline so far).
- [x] Batch-validate the whole scanner roster (multi-symbol forward tests) → blended OOS
      edge weight per scanner, persisted + applied live (`roster_service`, `blend_forward_tests`,
      `POST /backtests/validate-roster`, ML Lab edge-weights panel).
- [ ] Schedule the roster validation to re-run periodically (cron/worker) so edge weights
      stay fresh as regimes shift.
- [ ] Commit a real-data backtest-regression fixture under `tests/backtest_regression/`.
- [ ] Live-validate the Schwab OAuth round-trip once app credentials are configured
      (currently verified offline only).
- [ ] Option-chain backtests via Schwab real chains (gamma-regime-segmented).

## Known limitations / environment
- yfinance is unreachable in the sandbox (curl_cffi TLS vs the agent proxy); FMP and other
  `requests`-based vendors work fine through the proxy.
- Schwab OAuth can't be exercised live here (needs app credentials + browser consent).
- Docker/DB not available in-sandbox, so DB-backed E2E is validated via offline tests +
  DDL compile.

## Larger roadmap themes (see docs/ROADMAP.md)
- [ ] Paid market-data adapters: Polygon, Tradier, Theta, ORATS, CBOE.
- [ ] Internals/order-flow feeds (TICK/TRIN/VOLD, L2/tape) for the feed-gated scanners.
- [ ] Regime-segmented / options / portfolio backtesters.
- [ ] Continuous live paper-accumulation loop + forward-test PDF reports.
- [ ] Auth/RBAC, observability, experiment tracking, CI/CD, MASTER_KEY backup docs.
