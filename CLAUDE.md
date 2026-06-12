# CLAUDE.md — working in this repo

Guidance for AI agents and developers working on **Stock Wizard** (Python quant engine +
Svelte 5 dashboard). Read `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` first.

## Layout
- `engine/engine/` — pure domain engine (no web/DB imports). `schemas/` is the contract
  source of truth. `data/` adapters, `features/`, `scanners/`, `backtesting/`, `signals/`,
  `evidence/`, `ml/`, `reports/`, `risk/`.
- `packages/common/` — settings (pydantic-settings), Fernet crypto, tz/session utils.
- `storage/` — SQLAlchemy models + Alembic migrations (Timescale hypertables).
- `services/api/` — FastAPI app (`app/`); `services/worker/` — arq worker.
- `apps/web/` — SvelteKit 5 dashboard.
- `tests/` — unit, integration, backtest_regression, data_quality.

## Commands (via `just`)
- `just install` — `uv sync` + `pnpm install`
- `just up` / `just migrate` — Docker (Timescale+Redis) + Alembic
- `just api` / `just worker` / `just web` — run services
- `just test` — pytest · `just lint` — ruff + mypy · `just fmt` — ruff format
- `just check-web` — svelte-check

## Conventions
- **Contracts first.** Add/modify Pydantic models in `engine/engine/schemas/` and they flow
  to the API (OpenAPI) and UI (`just gen-types`). Prices are `Decimal`, datetimes tz-aware UTC.
- **Engine stays pure** — never import FastAPI/SQLAlchemy from `engine/`.
- **Adding a scanner:** subclass `engine.scanners.base.Scanner`, set `scanner_id/name/
  description/category/default_params/params_schema`, implement `run(ctx) -> ScannerResult`
  (always attach an `EvidencePacket`; use helpers in `scanners/_common.py`), then register it
  in `scanners/registry.py`. The parametrized smoke test (`tests/unit/test_all_scanners.py`)
  will automatically cover it. Tick its checkbox in `docs/ROADMAP.md`.
- **Every signal needs evidence** (why / why-now / for / against / invalidation). "No trade"
  is a valid, first-class result.
- **No lookahead** in backtests/ML — features use only past data; time-ordered splits only.
- After changes run `just fmt && just lint && just test` (and `just check-web` for UI).

## Ruff
Config in root `pyproject.toml`. Intentional ignores: B008 (FastAPI `Depends`), RUF012
(scanner config dicts), RUF001/2/3 (math glyphs σ/×/— in evidence text), UP042 (StrEnum base).

## Gotchas
- yfinance has no greeks/internals: greeks/GEX are computed (`features/greeks.py`,
  `features/gex.py`); internals are stubbed behind an adapter. SPX 0DTE chains are thin →
  gamma scanner is SPY-first (`underlying` param).
- TimescaleDB hypertables are created via raw SQL in the Alembic migration, not `create_all`.
- Vendor API keys are Fernet-encrypted with `MASTER_KEY` (env). Losing it is unrecoverable.

## Commit trailer
End commit messages with the session link the harness expects.
