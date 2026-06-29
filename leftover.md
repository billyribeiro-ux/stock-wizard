# Leftover — detailed handoff

Status snapshot of **Stock Wizard** at commit `73150b2` (branch `main`). This file is the
single place that records *what is done*, *what remains* (in detail, with file pointers and
acceptance criteria), the *known limitations* of the current environment, and *how to run /
reproduce* everything. Pair it with `CHANGELOG.md` (chronological) and `docs/ROADMAP.md` (the
exhaustive scanner/backtester/signal checklist). `TODO.md` is the short in-flight list.

---

## 1. Where things stand

The platform is complete and green end-to-end:

- **Data:** yfinance (free, keyless), **FMP** (primary equity feed, migrated to the FMP
  *stable* API), **Charles Schwab** (OAuth2 — equity OHLCV + real option chains with vendor
  greeks), SEC EDGAR (insider), Finnhub (congress/earnings/news). Adapter-driven; keys are
  Fernet-encrypted at rest and managed in Settings (add/rotate/rename/swap/delete).
- **Engine:** 57 scanners; feature factory (incl. `regime.er` Kaufman efficiency ratio);
  event-driven backtester with metrics, **regime breakdown**, walk-forward / forward test,
  Monte-Carlo, failure analysis, leakage audit.
- **Self-grading loop (the headline work):** roster validation forward-tests every
  OHLCV-backtestable scanner across a basket, blends per-symbol OOS results into a global +
  **per-(scanner, regime) edge weight**, persists them, and the **live signal path gates &
  weights each scanner by its current-regime out-of-sample edge**. A **regime-conditional
  ensemble** fuses regime-specialists and more than doubled the best single scanner OOS
  (+7424 vs +3541 on held-out data). Runnable live (`POST /scans/ensemble`, `/ensemble` UI)
  and re-validated weekly by an arq cron.
- **Services:** FastAPI app + arq worker; Postgres/Timescale + Redis.
- **Web:** SvelteKit 5 dashboard (Command Center, Scanners, **Ensemble**, Results, Backtest,
  Discovery, Replay, Forward, ML Lab, Self-Learning, Portfolio, Gamma, Alerts, Settings).
- **Quality:** ruff + mypy clean; **unit tests pass**; **integration e2e passes on a real
  Postgres/Redis stack**; web svelte-check + eslint + prettier clean.

The full evidence study (what was tested, adopted, and **rejected**) is in
`docs/BACKTESTS.md`.

---

## 2. Leftover work (detailed)

### 2.1 Operational / one-click (not code)
- [ ] **Set `main` as the GitHub default branch.** Currently the only branch and it holds all
      work, but the *default-branch* flag must be flipped in **GitHub → Settings → Branches**.
      The agent can't do this: org policy blocks the repo-settings API
      ("GitHub access is not enabled for this session") and no MCP tool exposes it.
- [ ] **Document `MASTER_KEY` backup/rotation.** Losing it makes every stored vendor key
      unrecoverable (by design). `MASTER_KEY_PREVIOUS` + a re-encrypt job already exist in the
      crypto layer; write the runbook (where the key lives, how to rotate, how to restore).
- [ ] **CI/CD.** No pipeline runs the suite on push. Add GitHub Actions: `uv sync` →
      `ruff check` + `mypy` + `pytest tests/unit`; spin up Postgres+Redis services for
      `pytest tests/integration`; `pnpm i && pnpm check && pnpm lint` for the web. The
      integration tests already skip cleanly when infra is absent.

### 2.2 Data vendors
- [ ] **Live-validate the Schwab OAuth round-trip.** The adapter, token refresh, and
      connect/exchange endpoints are implemented and unit-tested offline, but never exercised
      against the real Schwab API (needs app key/secret + a browser consent step). Walk the
      `/vendors/schwab/connect` → authorize → `/vendors/schwab/token` flow once and confirm a
      live `get_option_chain`. Files: `engine/data/schwab_source.py`,
      `services/api/app/services/schwab_creds.py`, `routers/vendors.py`.
- [ ] **Option-chain backtests via Schwab real chains** (gamma-regime-segmented). The gamma
      scanners (`spx_gamma_command`, `gamma_wall`, etc.) currently can't be roster-validated —
      the event-driven replay has no historical chains. With Schwab chains captured to the
      `option_chains` hypertable, build a chain-replay path so those scanners get OOS edge
      weights too.
- [ ] **Paid market-data adapters** (registry slots already declared, `notes="planned"`):
      Polygon, Tradier, Theta, ORATS, CBOE. Implement behind the existing capability
      Protocols in `engine/data/`.
- [ ] **Internals / order-flow feeds** (TICK/TRIN/VOLD/ADD, L2/tape). Several scanners are
      feed-gated and stubbed behind `internals_stub.py`. They need a real vendor to become
      tradeable (`market_breadth`, `arms_trin`, `mcclellan`, cumulative-delta, etc.).

### 2.3 Validation / ML deepening
- [ ] **Walk-forward-learned per-scanner exit & threshold params.** The exit policy (1.0 ATR
      stop, 1.5/3.0 targets) and `min_score` are global. Evidence so far says global is near
      optimal and naive tuning hurts (see `docs/BACKTESTS.md`), so any per-scanner params must
      be *in-sample optimised → OOS validated* (purged/embargoed) and only adopted if they
      beat the global baseline OOS. Don't hand-pick thresholds (overfitting).
- [ ] **Commit a real-data backtest-regression fixture** under `tests/backtest_regression/`
      (currently only `__init__.py`). Capture a small frozen OHLCV slice + golden metrics so
      regressions in the engine/scanners are caught in CI without a live feed.
- [ ] **Persist Schwab-chain greeks** into a gamma-scanner validation path so the gamma
      family joins the edge-weighted roster.

### 2.4 Research (grow the independent-edge set)
- [ ] **Validate genuinely independent edge families** so the ensemble has uncorrelated
      signals to fuse (the current proven set is momentum + range mean-reversion). Candidates:
      breadth/internals (needs feed), options-flow/gamma (needs chains), cross-asset/macro
      regime, calendar/seasonality. Each must clear the same per-regime OOS bar.
- [ ] **Re-run the full roster validation on a larger basket / longer history** and let the
      worker cron keep it fresh; tighten the borderline `keep_testing` calls
      (`breakout_quality`, `long_trap`, `regime_classification`).

### 2.5 Platform / ops
- [ ] **Continuous live paper-accumulation loop** + forward-test PDF reports / model cards
      (`docs/ROADMAP.md` Phase 7/8). The forward-test machinery exists; wire a scheduled
      paper-trade accumulation + a WeasyPrint report.
- [ ] **Auth/RBAC, observability/tracing, experiment tracking** (MLflow), orchestration
      (Prefect/Dagster) — `docs/ROADMAP.md` cross-cutting items, currently single-token auth.

See `docs/ROADMAP.md` for the full per-scanner checklist (28 open boxes, mostly feed-gated
scanners and later-phase platform items).

---

## 3. Known limitations & environment caveats

These are about the **sandbox/dev environment**, not the code:

- **Ephemeral Postgres/Redis.** The container's `pg_ctlcluster 16 main` and `redis-server`
  die on container restart and occasionally mid-session. Integration tests gate on both being
  reachable (`tests/integration/conftest.py` skips if not) — but if one dies *mid-run* the
  tests fail with a connection error rather than skipping. Restart with:
  `pg_ctlcluster 16 main start && redis-server --daemonize yes`.
- **No TimescaleDB extension** here. Migration `0001_initial` now probes
  `pg_available_extensions` and falls back to plain tables (hypertables only when Timescale is
  present) — so migrations run on vanilla Postgres. Production should use the
  `timescale/timescaledb-ha` image to get real hypertables.
- **Docker daemon is unavailable**, so testcontainers can't be used; the local cluster is the
  substitute.
- **yfinance is unreachable** — its curl_cffi backend doesn't honour the agent proxy CA
  bundle (TLS error). FMP and other `requests`-based vendors work fine through the proxy.
- **Schwab OAuth can't be live-tested** without app credentials + browser consent.
- **FMP API key.** The key used during this work was passed in chat and used only via the
  `FMP_KEY` env var — it is **not** in any tracked file (`git grep` clean). Rotate it if the
  transcript is shared.
- **Backtest results are a single ~3–5y window** (predominantly trending). Treat the numbers
  as relative scanner comparisons + no-lookahead validation, not absolute deployment edge;
  widen the basket/history before trusting magnitudes.

---

## 4. How to run / reproduce

### Local stack (this sandbox)
```bash
pg_ctlcluster 16 main start && redis-server --daemonize yes
export DATABASE_URL="postgresql+asyncpg://wizard:wizard@localhost:5432/stockwizard"
export DATABASE_URL_SYNC="postgresql+psycopg://wizard:wizard@localhost:5432/stockwizard"
export REDIS_URL="redis://localhost:6379/0"
export INTERNAL_API_TOKEN="test-token"
export MASTER_KEY="ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg="   # dev-only Fernet key
cd storage && uv run alembic upgrade head && cd ..
```

### Checks (what CI should run)
```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest tests/unit -q                 # unit (no infra)
uv run pytest tests/integration -q          # e2e (needs PG+Redis; skips if absent)
cd apps/web && pnpm run check && pnpm run lint
```

### Run the services
```bash
just api      # uvicorn FastAPI
just worker   # arq worker (incl. weekly roster-validation cron)
just web      # SvelteKit dev server
```

### Validate the roster + run the ensemble (the headline flow)
1. Add an FMP key in **Settings** (or `POST /vendors/keys`).
2. ML Lab → **validate roster** (or `POST /backtests/validate-roster`) — forward-tests the
   roster, persists per-regime edge weights (visible in the ML Lab edge-weights panel).
3. **/ensemble** → pick ≥2 scanners + symbols → **Run Ensemble** (or `POST /scans/ensemble`).
   Each scanner is weighted by its current-regime OOS edge; the consensus signal lands in
   Results.

### Scratch analysis scripts (not committed)
The ad-hoc measurement scripts used to produce `docs/BACKTESTS.md` live under the session
scratchpad (evidence diagnostic, exit-policy sweep, min_score sweep, regime-edge measurement,
ensemble comparison, roster runner). They use `FMP_KEY` + the engine directly (no DB). Re-home
them under `scripts/research/` if they should be kept.

---

## 5. Key file map (for whoever picks this up)

- Per-regime edge weights: `engine/backtesting/roster.py` (`blend_forward_tests`,
  `_regime_edges`), persisted via `repositories/repo.py`
  (`save_walkforward_edge` / `get_latest_edge_record` / `list_edge_weights`).
- Live gating/weighting: `engine/signals/builder.py` (regime gate + edge gate +
  regime-conditional weight), `engine/scanners/regime_affinity.py`.
- Regime classifier: `engine/features/regime.py` (efficiency ratio), surfaced as
  `regime.er` in `engine/features/factory.py`.
- Ensemble: `engine/backtesting/ensemble_bt.py` (backtest) +
  `services/api/app/services/ensemble_service.py` (live) + `routers/scans.py`
  (`POST /scans/ensemble`) + `apps/web/src/routes/ensemble/`.
- Roster validation + cron: `services/api/app/services/roster_service.py`,
  `services/worker/worker/{tasks,main}.py`.
- Data adapters: `engine/data/{fmp_source,schwab_source,yfinance_source,...}.py`,
  `engine/data/registry.py`.
- Evidence study + all measured results: `docs/BACKTESTS.md`.
