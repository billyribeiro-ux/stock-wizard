# Stock Wizard — Master Roadmap & Build Checklist

The single source of truth for *what exists* and *what's next*. Every scanner, backtester,
and signal generator from the blueprint is a checkbox here. Tick items as they ship.

**Legend:** ✅ done · 🚧 in progress · ⬜ todo
**Schema version:** `1.0.0` · **Last updated:** 2026-06-11

> Principle: **no evidence, no signal; conflicting evidence, no trade; proven evidence,
> higher confidence.** Nothing is "trusted" until it survives walk-forward + forward testing.

---

## Build Phases

### Phase 0 — Scaffold & Contracts ✅
- [x] Monorepo (uv + pnpm workspaces), docker-compose (Timescale + Redis), justfile, env template
- [x] Canonical Pydantic v2 contracts: MarketBar/OHLCV, OptionChain, FeatureSnapshot, ScannerResult, SignalPacket, EvidencePacket, BacktestResult, ReportSpec, catalyst (insider/congress/earnings/news)
- [x] JSON-Schema exporter for TS type generation (`engine.schemas.export_jsonschema`)
- [x] Unit tests for the contract layer

### Phase 1 — Data Layer 🚧
- [x] Adapter-driven `DataSource` protocols + vendor registry (Settings-key aware)
- [x] yfinance OHLCV + option-chain adapter
- [x] SEC EDGAR insider (Form 4) adapter — keyless
- [x] Finnhub adapter — insider, congress, earnings, news (keyed)
- [x] Market-internals stub (TICK/TRIN/VOLD/ADD) behind the real interface
- [x] Data validation (gaps, splits, zero-vol, out-of-hours, impossible)
- [x] Postgres/TimescaleDB models + Alembic migration (hypertables: ohlcv, internals, option_chains)
- [x] Persist ingested OHLCV bars to Timescale (upsert) + /health data-health
- [ ] Persist option chains; continuous aggregates (1m→5m→1h), compression + retention
- [ ] Paid market-data adapters: Polygon, Tradier, Theta, ORATS, CBOE

### Phase 2 — Feature Factory ✅ (core)
- [x] ATR, true range
- [x] RVOL, rolling volume slope, up/down volume, volume dry-up
- [x] Session VWAP + Anchored VWAP
- [x] Volume Profile (POC / VAH / VAL)
- [x] Market structure (swings, HH/HL/LH/LL, BOS, CHoCH)
- [x] Black-Scholes greeks + IV solver (golden-tested)
- [x] GEX by strike, gamma walls, gamma flip (golden-tested)
- [ ] Internals features (needs a real internals feed)
- [ ] Catalyst / time-of-day / regime feature families (expansion)

### Phase 3 — Scanner Engine 🚧  (see catalog below)
- [x] Scanner base + registry + ScanContext
- [x] 44 scanners live: structure/levels/price-action/volume + full gamma family +
      cross-asset/VIX/sector + volatility/seasonality + insider/congress + earnings + ML
- [ ] Remaining scanners need external feeds: order-flow/L2/tape, market internals
      (TICK/TRIN/VOLD), VIX options; plus research scanners (genetic/Bayesian/RL)

### Phase 4 — Signals & Evidence ✅ (core)
- [x] ScannerResult → SignalPacket builder with ATR trade plan
- [x] Invalidation engine (price/time/structure/options rules)
- [x] Evidence packets on every result
- [x] Ensemble / conflict resolver (consensus + no-trade)
- [ ] Calibrated confidence + regime permissions (ML phase)

### Phase 5 — Backtesting Lab 🚧  (see catalog below)
- [x] `BacktestResult` contract locked + event-driven engine + metrics
- [x] Backtest Lab UI + /backtests API + worker task
- [x] Walk-forward validation + Monte-Carlo bootstrap stress
- [ ] Regime-segmented, options/multi-leg, portfolio backtesters

### Phase 6 — Forward Testing & Live Feed 🚧
- [x] Redis pub/sub signal channel + FastAPI SSE stream
- [x] SvelteKit `query.live` live signal feed
- [x] Forward (paper) test: in/out-of-sample split, drift, Monte-Carlo, promotion decision
      (promote / keep_testing / retire) via /backtests mode=forward
- [ ] Continuous live paper accumulation loop

### Phase 7 — ML & Self-Learning 🚧
- [x] As-of-safe dataset/label builder, GB setup-success model with walk-forward
      (time-ordered) split, feature importance, AUC/Brier/calibration, reliability gate
- [x] Anomaly detection (IsolationForest) + regime classification (KMeans) scanners
- [x] /ml/train API + worker task + model_registry persistence
- [ ] Genetic rule miner, Bayesian scorer, RL policy lab, automated failure-analysis loop

### Phase 8 — Reports & Export ✅ (core)
- [x] CSV export (scanner results, signals, backtest trades)
- [x] PDF evidence report + PDF backtest report (WeasyPrint + Jinja2)
- [ ] PDF forward-test report, model cards, feature dumps

### Phase 9 — Dashboard ✅ (v1)
- [x] Command Center, Scanner Builder, Results, Evidence Viewer, Settings (vendor keys)
- [x] Phosphor icons (Iconify CSS), ECharts gamma chart, live LIVE indicator
- [x] Backtest Lab (equity curve + metrics + trades), SPX 0DTE Gamma Lab
- [x] ML Lab (train model, feature importance, calibration), Portfolio/Watchlist
- [x] Forward Test Lab (promotion verdict, drift, Monte-Carlo, walk-forward)
- [x] Scanner Builder grouped/filterable across all 43 scanners by category
- [ ] Trade Replay

### Phase 10 — Hardening & Desktop 🚧
- [x] CI/CD (GitHub Actions: ruff + pytest, svelte-check + build)
- [x] **Desktop app (Tauri)** scaffold (`apps/desktop`) wrapping the SvelteKit UI with
      FastAPI as a bundled sidecar (needs Rust toolchain to compile)
- [ ] Auth/RBAC, audit logs, observability, data-quality alarms
- [ ] Reproducible experiment tracking (MLflow), orchestration (Prefect/Dagster)

---

## §6 Scanner Catalog (~66)

### 6.1 Market structure / levels / price-action / volume (27)
- [x] Multi-Timeframe Market Structure
- [x] Volume Profile POC/VAH/VAL
- [x] Key Level Intelligence
- [x] Anchored VWAP Institutional Level
- [x] Opening Range & Session Timing
- [x] Gap & Gap-Fill
- [x] Liquidity Sweep / Stop-Hunt
- [x] Short Trap
- [x] Long Trap
- [x] Pullback Reason Classifier
- [x] Breakout Quality
- [x] Reversal Master
- [x] Trend Exhaustion
- [x] Momentum Ignition
- [x] Bigger-Than-Expected Move Detector
- [x] Squeeze & Compression
- [x] Failed Move
- [x] Subtle Accumulation/Distribution
- [x] Volume Divergence / Effort-vs-Result
- [ ] Cumulative Delta / Order Flow (needs L2/tick feed)
- [ ] Large Print & Block Activity (needs tape feed)
- [ ] Micro POC Per-Bar Auction (needs tick feed)
- [ ] Bid/Ask Imbalance (needs L2 feed)
- [ ] Absorption (needs tick/delta feed)
- [x] Low-Volume Pullback
- [x] Volume Dry-Up Reversal
- [x] Relative Volume Expansion

### 6.2 Options / gamma / SPX (14)
- [x] SPX 0DTE Gamma Command
- [x] Gamma Exposure / GX
- [x] Gamma Hedge Wall
- [x] Gamma Squeeze
- [x] Dealer Hedge Flow
- [x] Options Flow & Unusual Activity
- [ ] VIX Options Hedge (needs VIX options feed)
- [x] Expected Move & IV Premium
- [x] Pin Risk & Magnet
- [x] Charm & Vanna Flow
- [x] Skew & Term Structure
- [ ] 0DTE Scalp-vs-Reversal Classifier (covered by Gamma Command)
- [x] Broken Wing Butterfly Opportunity
- [x] Max Pain & OI Cluster

### 6.3 Internals / volatility / sector / cross-asset (8)
- [ ] Market Internals Breadth (needs TICK/TRIN/VOLD feed)
- [ ] TICK Extremes & Divergence (needs internals feed)
- [ ] TRIN & VOLD Confirmation (needs internals feed)
- [x] VIX/VVIX/MOVE Tail Risk
- [x] Volatility Regime
- [x] Sector Rotation & Leadership
- [x] Index Leadership Divergence
- [x] Cross-Asset Risk-On/Risk-Off

### 6.4 Catalyst / calendar / analog (5 + extensions)
- [x] **Insider & Congress Flow** _(added: SEC EDGAR + Finnhub)_
- [ ] Catalyst & News Event
- [ ] Economic Calendar
- [x] Earnings & Guidance (Finnhub: event risk + post-earnings drift)
- [x] Seasonality & Similar-Day
- [ ] Macro Regime

### 6.5 ML / self-learning / research (12)
- [x] Pattern Discovery (KMeans regime clustering)
- [x] Feature Importance & Evidence Miner (GB model importances)
- [x] Anomaly Detection (IsolationForest scanner)
- [x] Regime Classification Engine (scanner + forward-bias)
- [ ] Genetic Rule Miner
- [ ] Bayesian Evidence Scorer
- [ ] Reinforcement Learning Trade Policy Lab
- [ ] Failure Analysis
- [x] Confidence Calibration (reliability curve + Brier in model report)
- [x] Signal Conflict Resolver _(v1 ensemble; ML upgrade pending)_
- [x] Self-Learning Label Builder (forward-return dataset builder)
- [ ] User Rule Builder & Hypothesis Lab

---

## §8 Backtester Catalog
- [x] `BacktestResult` contract + metrics locked
- [x] Event-Driven backtester (no-lookahead, ATR plan, commission + slippage, full metrics)
- [x] Walk-Forward Validation · Monte-Carlo / Bootstrap stress · Forward (paper) test
- [ ] Tick/1s/1m multi-bar · Vectorized research
- [ ] SPX 0DTE Options · Multi-Leg Options (BWB) · Gamma Regime
- [ ] Market Internals Confirmation · Volume Profile / Auction · Catalyst Event
- [ ] Walk-Forward Validation · Monte Carlo / Bootstrap · Slippage/Commission/Spread
- [ ] Forward Testing / Paper · Portfolio / Long-Term · Signal Ensemble · Regime-Segmented
- [ ] Trade Replay · Lookahead/Leakage Auditor · Data-Quality Auditor

## §9 Signal Generator Catalog
- [x] Universal `SignalPacket` schema + builder + invalidation
- [x] No-Trade / Danger-Zone as a first-class signal
- [x] **Alert engine**: rules (scanner/side/score/symbol/classification) → dispatch
      (log / webhook / email-stub), events recorded; evaluated on every triggered signal
- [ ] Scalp L/S · Day-Trade Continuation · Top/Bottom Reversal · Pullback Continuation
- [ ] Short-Trap Long · Long-Trap Short · Gamma Squeeze · Hedge-Wall Rejection
- [ ] SPX 0DTE Directional Scalp · SPX 0DTE Reversal/Top/Bottom · BWB Candidate
- [ ] Swing Continuation · Swing Reversal · Long-Term Accumulation/Distribution

---

## Cross-cutting
- [x] Vendor API-key store (Fernet-encrypted, masked, rotation-ready)
- [x] Vendor registry exposed to Settings (yfinance, SEC EDGAR, Finnhub + planned slots)
- [ ] Observability / tracing · Auth/RBAC · CI/CD · Backup of MASTER_KEY documented
