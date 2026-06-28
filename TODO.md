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
- [ ] Investigate `trend_exhaustion` and `squeeze_compression` triggering 0 trades at
      `min_score=0.35` (threshold/condition review).
- [ ] Walk-forward + regime-segmented backtests (current baseline is a single ~3y window).
- [ ] Wire the FMP key into a Settings entry end-to-end and confirm a live scan uses it.
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
