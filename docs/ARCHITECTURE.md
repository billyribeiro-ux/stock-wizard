# Architecture

## Overview

```
                ┌──────────────────────────────┐
   Browser ───▶ │  SvelteKit (Svelte 5, runes) │   apps/web
   Desktop ───▶ │  remote functions + query.live│
   (Tauri)      └───────────────┬──────────────┘
                                 │  server-only fetch ($env private, INTERNAL_API_TOKEN)
                                 ▼
                ┌──────────────────────────────┐
                │  FastAPI  (services/api)      │  REST + SSE  ── enqueue ──▶ arq worker
                └───────────────┬──────────────┘                           (services/worker)
                                │ imports
                                ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  engine/  (pure, importable; no web/db deps)                      │
   │  schemas → data adapters → features → scanners → signals/evidence │
   │  → backtesting → reports → risk                                   │
   └───────────────┬─────────────────────────────────┬───────────────┘
                   ▼                                   ▼
        Postgres + TimescaleDB                      Redis
   (ohlcv/internals/option_chains hypertables;   (arq queue, signal pub/sub,
    scans/signals/evidence/vendor_keys)           cache, rate-limit buckets)
```

## Principles
- **Contracts first.** `engine/engine/schemas/` Pydantic v2 models are the single source of
  truth. FastAPI's OpenAPI and the TS types (via `just gen-types`) derive from them, so the
  Python engine and the dashboard cannot drift.
- **Engine is pure.** `engine/` has no FastAPI/DB imports — it's unit-testable offline and
  reusable by API, worker, notebooks, and (later) the desktop sidecar.
- **Adapter-driven data.** Every vendor implements small capability protocols
  (`OhlcvSource`, `OptionSource`, `InsiderSource`, `CongressSource`, …). yfinance + SEC EDGAR
  are keyless; Finnhub and paid vendors plug in via the encrypted Settings key store.
- **Evidence on everything.** No signal is a bare arrow: each carries why / why-now /
  for / against / invalidation / analogs. "No trade" is a first-class signal.

## Data & compute flow (one scan)
1. `POST /scans` creates a `scan_runs` row, enqueues an arq job (or runs inline if Redis is down).
2. Worker `run_scan` → `execute_scan`: resolve `DataSource` (vendor key decrypted on demand) →
   fetch OHLCV (+HTF / option chain / insider+congress as the scanner needs) → `validate` →
   `FeatureFactory.build_snapshot` → `scanner.run(ctx)` → persist `ScannerResult` + `SignalPacket`.
3. Triggered signals are published to Redis `signals:{run_id}`.
4. FastAPI `/stream/signals` (SSE) relays the channel; SvelteKit `query.live` renders it live.

## Security: vendor API keys
- `MASTER_KEY` (Fernet, 32-byte base64) from env / host secret manager — read only server-side.
- Keys arrive over TLS → encrypted at rest in `vendor_keys.ciphertext`; reads return a masked
  `••••1234`; plaintext is decrypted only at adapter instantiation.
- `key_version` + `MASTER_KEY_PREVIOUS` enable rotation. **Losing `MASTER_KEY` is unrecoverable
  by design** — back it up in your secret manager.

## The SPX 0DTE gamma math (why it's trustworthy)
- Per-contract gamma `Γ = N'(d1)/(S·σ·√T)` (closed form, pinned by a golden test).
- `GEX(K) = Γ(K)·OI(K)·100·S²·0.01·sign` (dealer convention: calls +, puts −).
- **Flip / zero-gamma** = the spot where the *total* gamma profile (recomputed across a spot
  grid, IVs fixed) crosses zero. Walls = largest |net GEX| strikes above/below spot.
- Guards: `T` floored, `σ>0`, zero-OI skipped; degraded chains flagged in evidence.
- yfinance SPX 0DTE coverage is thin → the scanner is **SPY-first** (`underlying` is a param);
  Tradier/Polygon/Theta are the first real-data upgrades.

## Web + Desktop
- **Web** (primary): SvelteKit `adapter-node` + FastAPI + Postgres/Redis.
- **Desktop** (planned, Phase 10): the same SvelteKit UI wrapped in **Tauri**, with the FastAPI
  engine shipped as a bundled **sidecar** process. Because FastAPI owns the real API and the
  SvelteKit layer is thin (server-only API client + replaceable remote functions), the desktop
  build reuses the web UI unchanged; a static/SPA build path is the fallback if the node server
  isn't bundled.

## Repo layout
- `engine/` — domain engine (schemas, data, features, scanners, signals, evidence, backtesting, reports, risk)
- `packages/common/` — settings, Fernet crypto, timezone/session utils
- `storage/` — SQLAlchemy models + Alembic migrations (Timescale hypertables)
- `services/api/` — FastAPI app; `services/worker/` — arq worker
- `apps/web/` — SvelteKit dashboard
- `tests/` — unit, integration, backtest_regression, data_quality
