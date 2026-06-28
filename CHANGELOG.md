# Changelog

All notable changes to **Stock Wizard** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project is pre-1.0 and versions track development waves rather than semver releases.

## [Unreleased]

### Added
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
- `pytest` 276 unit tests pass; full lint/type/web-check suite clean.
