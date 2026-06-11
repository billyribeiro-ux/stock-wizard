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
- [ ] Persist ingested bars/chains to Timescale (write path) 🚧
- [ ] Continuous aggregates (1m→5m→1h), compression + retention policies
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
- [x] 3 POC scanners + Insider/Congress flow scanner
- [ ] Remaining ~60 scanners from the catalog

### Phase 4 — Signals & Evidence ✅ (core)
- [x] ScannerResult → SignalPacket builder with ATR trade plan
- [x] Invalidation engine (price/time/structure/options rules)
- [x] Evidence packets on every result
- [x] Ensemble / conflict resolver (consensus + no-trade)
- [ ] Calibrated confidence + regime permissions (ML phase)

### Phase 5 — Backtesting Lab ⬜  (see catalog below)
- [ ] Contract `BacktestResult` locked ✅; engine implementation pending

### Phase 6 — Forward Testing & Live Feed 🚧
- [x] Redis pub/sub signal channel + FastAPI SSE stream
- [x] SvelteKit `query.live` live signal feed
- [ ] Paper-trading engine + drift monitoring + promotion gate

### Phase 7 — ML & Self-Learning ⬜
- [ ] Label builder, feature importance, pattern discovery, regime classifier,
      anomaly detection, genetic rule miner, Bayesian scorer, RL policy lab,
      failure-analysis loop, confidence calibration

### Phase 8 — Reports & Export ✅ (core)
- [x] CSV export (scanner results, signals)
- [x] PDF evidence report (WeasyPrint + Jinja2)
- [ ] PDF backtest / forward-test reports, model cards, feature dumps

### Phase 9 — Dashboard ✅ (v1)
- [x] Command Center, Scanner Builder, Results, Evidence Viewer, Settings (vendor keys)
- [x] Phosphor icons (Iconify CSS), ECharts gamma chart, live LIVE indicator
- [ ] Backtest Lab, Forward Test Lab, SPX 0DTE Gamma Lab, Trade Replay, ML Lab, Portfolio/Swing

### Phase 10 — Hardening & Desktop ⬜
- [ ] Auth/RBAC, audit logs, observability, CI/CD, data-quality alarms
- [ ] **Desktop app (Tauri)** wrapping the SvelteKit UI with FastAPI as a bundled sidecar
- [ ] Reproducible experiment tracking (MLflow), orchestration (Prefect/Dagster)

---

## §6 Scanner Catalog (~66)

### 6.1 Market structure / levels / price-action / volume (27)
- [x] Multi-Timeframe Market Structure
- [x] Volume Profile POC/VAH/VAL
- [ ] Key Level Intelligence
- [ ] Anchored VWAP Institutional Level
- [ ] Opening Range & Session Timing
- [ ] Gap & Gap-Fill
- [ ] Liquidity Sweep / Stop-Hunt
- [ ] Short Trap
- [ ] Long Trap
- [ ] Pullback Reason Classifier
- [ ] Breakout Quality
- [ ] Reversal Master
- [ ] Trend Exhaustion
- [ ] Momentum Ignition
- [ ] Bigger-Than-Expected Move Detector
- [ ] Squeeze & Compression
- [ ] Failed Move
- [ ] Subtle Accumulation/Distribution
- [ ] Volume Divergence / Effort-vs-Result
- [ ] Cumulative Delta / Order Flow
- [ ] Large Print & Block Activity
- [ ] Micro POC Per-Bar Auction
- [ ] Bid/Ask Imbalance
- [ ] Absorption
- [ ] Low-Volume Pullback
- [ ] Volume Dry-Up Reversal
- [ ] Relative Volume Expansion

### 6.2 Options / gamma / SPX (14)
- [x] SPX 0DTE Gamma Command
- [ ] Gamma Exposure / GX
- [ ] Gamma Hedge Wall
- [ ] Gamma Squeeze
- [ ] Dealer Hedge Flow
- [ ] Options Flow & Unusual Activity
- [ ] VIX Options Hedge
- [ ] Expected Move & IV Premium
- [ ] Pin Risk & Magnet
- [ ] Charm & Vanna Flow
- [ ] Skew & Term Structure
- [ ] 0DTE Scalp-vs-Reversal Classifier
- [ ] Broken Wing Butterfly Opportunity
- [ ] Max Pain & OI Cluster

### 6.3 Internals / volatility / sector / cross-asset (8)
- [ ] Market Internals Breadth
- [ ] TICK Extremes & Divergence
- [ ] TRIN & VOLD Confirmation
- [ ] VIX/VVIX/MOVE Tail Risk
- [ ] Volatility Regime
- [ ] Sector Rotation & Leadership
- [ ] Index Leadership Divergence
- [ ] Cross-Asset Risk-On/Risk-Off

### 6.4 Catalyst / calendar / analog (5 + extensions)
- [x] **Insider & Congress Flow** _(added: SEC EDGAR + Finnhub)_
- [ ] Catalyst & News Event
- [ ] Economic Calendar
- [ ] Earnings & Guidance
- [ ] Seasonality & Similar-Day
- [ ] Macro Regime

### 6.5 ML / self-learning / research (12)
- [ ] Pattern Discovery
- [ ] Feature Importance & Evidence Miner
- [ ] Anomaly Detection
- [ ] Regime Classification Engine
- [ ] Genetic Rule Miner
- [ ] Bayesian Evidence Scorer
- [ ] Reinforcement Learning Trade Policy Lab
- [ ] Failure Analysis
- [ ] Confidence Calibration
- [x] Signal Conflict Resolver _(v1 ensemble; ML upgrade pending)_
- [ ] Self-Learning Label Builder
- [ ] User Rule Builder & Hypothesis Lab

---

## §8 Backtester Catalog
- [x] `BacktestResult` contract + metrics locked
- [ ] Event-Driven Intraday · Tick/1s/1m multi-bar · Vectorized research
- [ ] SPX 0DTE Options · Multi-Leg Options (BWB) · Gamma Regime
- [ ] Market Internals Confirmation · Volume Profile / Auction · Catalyst Event
- [ ] Walk-Forward Validation · Monte Carlo / Bootstrap · Slippage/Commission/Spread
- [ ] Forward Testing / Paper · Portfolio / Long-Term · Signal Ensemble · Regime-Segmented
- [ ] Trade Replay · Lookahead/Leakage Auditor · Data-Quality Auditor

## §9 Signal Generator Catalog
- [x] Universal `SignalPacket` schema + builder + invalidation
- [x] No-Trade / Danger-Zone as a first-class signal
- [ ] Scalp L/S · Day-Trade Continuation · Top/Bottom Reversal · Pullback Continuation
- [ ] Short-Trap Long · Long-Trap Short · Gamma Squeeze · Hedge-Wall Rejection
- [ ] SPX 0DTE Directional Scalp · SPX 0DTE Reversal/Top/Bottom · BWB Candidate
- [ ] Swing Continuation · Swing Reversal · Long-Term Accumulation/Distribution

---

## Cross-cutting
- [x] Vendor API-key store (Fernet-encrypted, masked, rotation-ready)
- [x] Vendor registry exposed to Settings (yfinance, SEC EDGAR, Finnhub + planned slots)
- [ ] Observability / tracing · Auth/RBAC · CI/CD · Backup of MASTER_KEY documented
