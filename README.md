# Ultimate Self-Learning Trading Scanner, Backtester & Signal Engine

A Python quant engine + Svelte 5 / SvelteKit dashboard for an all-in-one trading **scanner,
backtester, forward-tester, signal generator, and self-learning research engine**.

> Status: **Phase 0–1 foundation + v1 vertical slice.** See [`docs/ROADMAP.md`](docs/ROADMAP.md)
> for the full multi-phase checklist (every scanner, backtester, and signal generator from the
> blueprint), and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.

## What works in v1

- Canonical Pydantic v2 contracts shared across the engine (`MarketBar`, `OptionChain`,
  `FeatureSnapshot`, `ScannerResult`, `SignalPacket`, `EvidencePacket`, `BacktestResult`, `ReportSpec`).
- yfinance-first data layer behind a vendor-agnostic adapter interface (paid vendors plug in later
  via the Settings API-key panel).
- Feature factory: ATR, swing/market-structure, RVOL, VWAP/AVWAP, volume profile, Black-Scholes
  greeks, and GEX-by-strike / gamma walls / gamma flip.
- Three proof-of-concept scanners — **Multi-Timeframe Market Structure**, **Volume Profile
  POC/VAH/VAL**, and the **SPX 0DTE Gamma Command** engine — each emitting a `ScannerResult` with a
  full `EvidencePacket`.
- FastAPI backend + arq worker, Postgres/TimescaleDB + Redis storage, encrypted vendor API keys.
- CSV + PDF export.
- SvelteKit command-center dashboard (Command Center, Scanner Builder, Results, Evidence Viewer,
  Settings) with live signal streaming and Phosphor icons.

## Stack

- **Engine / API:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, arq, yfinance,
  py_vollib, WeasyPrint. Managed with **uv** (workspace).
- **Storage:** Postgres + **TimescaleDB** (hypertables) + **Redis**.
- **Frontend:** Svelte 5 (runes) + SvelteKit (remote functions), TypeScript, Tailwind v4, Phosphor
  icons (via Iconify CSS), ECharts. Managed with **pnpm**.

## Deployment targets

- **Web app** (primary): SvelteKit (`adapter-node`) + FastAPI.
- **Desktop app** (planned): the same SvelteKit UI wrapped with **Tauri**, with the FastAPI engine
  running as a bundled sidecar. The frontend keeps a plain typed REST client so it can also build as
  a static SPA for the desktop shell. See `docs/ARCHITECTURE.md`.

## Quick start

```bash
cp .env.example .env            # then set MASTER_KEY (see comment in file) and INTERNAL_API_TOKEN
just install                    # uv sync + pnpm install
just up                         # start TimescaleDB + Redis (docker)
just migrate                    # create tables + hypertables
just api                        # FastAPI on :8000
just worker                     # arq worker (separate shell)
just web                        # SvelteKit dev on :5173 (separate shell)
just test                       # run the Python test suite
```
