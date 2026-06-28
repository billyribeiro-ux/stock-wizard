// Hand-written TypeScript interfaces mirroring the FastAPI backend's Pydantic
// models. A real generation step exists later in the pipeline; for now these
// are the source of truth on the frontend. Keep field names in sync with the
// API contract documented in the backend.

export type Direction = 'LONG' | 'SHORT' | 'NEUTRAL';
export type Side = 'LONG' | 'SHORT' | 'NEUTRAL';
export type EvidenceDirection = 'for' | 'against';

export interface EvidenceItem {
	kind: string;
	label: string;
	value: unknown;
	weight: number;
	direction: EvidenceDirection;
	source: string;
}

export interface Analog {
	date: string;
	symbol: string;
	similarity: number;
	outcome?: string;
	forward_return?: number;
}

export interface EvidencePacket {
	why: string;
	why_now: string;
	evidence_for: EvidenceItem[];
	evidence_against: EvidenceItem[];
	invalidation: string;
	historical_analogs: Analog[];
	confidence: number;
}

export interface ScannerResult {
	scanner_id: string;
	symbol: string;
	timeframe: string;
	ts: string;
	triggered: boolean;
	direction?: Direction;
	score: number;
	classification: string;
	levels: Record<string, number>;
	evidence: EvidencePacket;
	params: Record<string, unknown>;
	run_id: string;
	/** server-assigned identifier, present on results returned by /results/{id} */
	id?: string;
	/** optional extra payload some scanners attach (e.g. per-strike GEX) */
	meta?: Record<string, unknown>;
}

export interface SignalPacket {
	signal_id: string;
	run_id: string;
	source_scanner: string;
	symbol: string;
	asset_class: string;
	timeframe: string;
	side: Side;
	state: string;
	score: number;
	regime: string;
	/** false when the source scanner has no validated edge in the current regime (gated) */
	regime_aligned?: boolean;
	/** validated edge multiplier (1.0 = neutral, >1 proven, <1 under-performing) */
	edge_weight?: number;
	entry: number;
	stop: number;
	targets: number[];
	key_levels: Record<string, number>;
	evidence: EvidencePacket;
	expires_at?: string;
	created_at: string;
}

export interface DataHealthEntry {
	symbol: string;
	timeframe: string;
	last_bar_age_seconds: number;
}

export interface HealthResponse {
	status: string;
	db: string;
	redis: string;
	timescale: string;
	data_health: DataHealthEntry[];
}

/** A field within a scanner's JSON-schema params definition. */
export interface JsonSchemaProperty {
	type?: 'string' | 'number' | 'integer' | 'boolean' | 'array' | 'object';
	title?: string;
	description?: string;
	default?: unknown;
	enum?: (string | number)[];
	minimum?: number;
	maximum?: number;
	items?: JsonSchemaProperty;
}

export interface JsonSchema {
	type?: string;
	title?: string;
	properties?: Record<string, JsonSchemaProperty>;
	required?: string[];
}

/** Broad grouping the engine assigns each scanner. */
export type ScannerCategory =
	| 'structure'
	| 'volume'
	| 'options_gamma'
	| 'volatility'
	| 'catalyst'
	| 'ml'
	| string;

export interface Scanner {
	scanner_id: string;
	name: string;
	description: string;
	params_schema: JsonSchema;
	/** Broad grouping used to organize the scanner picker. */
	category?: ScannerCategory;
	/** Default parameter values declared by the scanner. */
	default_params?: Record<string, unknown>;
}

export type ScanStatus = 'queued' | 'running' | 'finished' | 'error' | string;

export interface ScanRun {
	run_id: string;
	scanner_id: string;
	status: ScanStatus;
	created_at: string;
	finished_at?: string | null;
	error?: string | null;
}

export interface ScannerResultsResponse {
	items: ScannerResult[];
	total: number;
}

export interface SignalsResponse {
	items: SignalPacket[];
}

export interface Vendor {
	id: string;
	vendor: string;
	label: string;
	masked_key: string;
	enabled: boolean;
	scopes: string[];
	/** Monotonically increasing version, bumped each time the secret is rotated. */
	key_version?: number;
	last_used_at?: string | null;
}

/** Backwards-compatible alias for a stored vendor key. */
export type VendorKey = Vendor;

/** A vendor the engine can source data from (GET /vendors/catalog). */
export interface VendorCatalogEntry {
	vendor: string;
	label: string;
	requires_key: boolean;
	capabilities: string[];
	docs_url?: string | null;
	notes?: string | null;
}

export interface ReportSpec {
	run_id?: string;
	result_ids?: string[];
	format: 'csv' | 'pdf';
	title?: string;
	[key: string]: unknown;
}

// --- Backtests ---------------------------------------------------------------

/** A single closed trade produced by a backtest run. */
export interface TradeRecord {
	symbol: string;
	side: Side;
	entry_ts: string;
	entry_price: number;
	exit_ts: string;
	exit_price: number;
	pnl: number;
	return_pct: number;
	mfe: number;
	mae: number;
	hold_seconds: number;
	exit_reason: string;
}

/** A point on the equity curve, with running drawdown. */
export interface EquityPoint {
	ts: string;
	equity: number;
	drawdown: number;
}

/** Aggregate performance metrics for a backtest. */
export interface BacktestMetrics {
	total_trades: number;
	win_rate: number;
	profit_factor: number;
	expectancy: number;
	total_pnl: number;
	cagr: number;
	sharpe: number;
	sortino: number;
	max_drawdown: number;
	recovery_factor: number;
	avg_win: number;
	avg_loss: number;
	avg_rr: number;
	exposure: number;
}

/** Full result payload of a finished backtest. */
export interface BacktestResult {
	trades: TradeRecord[];
	equity_curve: EquityPoint[];
	metrics: BacktestMetrics;
	period_start: string;
	period_end: string;
}

export type BacktestStatus = 'queued' | 'running' | 'done' | 'error' | string;

/** Summary row for the "past backtests" list (GET /backtests). */
export interface BacktestSummary {
	backtest_id: string;
	scanner_id: string;
	timeframe: string;
	universe: string[];
	status: BacktestStatus;
	metrics?: BacktestMetrics | null;
	created_at: string;
}

/** Full backtest record (GET /backtests/{id}). */
export interface Backtest {
	backtest_id: string;
	scanner_id: string;
	status: BacktestStatus;
	timeframe: string;
	universe: string[];
	params: Record<string, unknown>;
	metrics?: BacktestMetrics | null;
	result?: BacktestResult | null;
	error?: string | null;
	created_at: string;
	finished_at?: string | null;
}

export interface BacktestsResponse {
	items: BacktestSummary[];
}

// --- Forward tests -----------------------------------------------------------

/** Recommendation produced by a forward test. */
export type Promotion = 'promote' | 'keep_testing' | 'retire' | string;

/** Monte-Carlo resampling summary over the out-of-sample trades. */
export interface MonteCarloReport {
	prob_profit: number;
	median_return: number;
	p05_return: number;
	p95_return: number;
	median_max_dd: number;
	worst_max_dd: number;
}

/** One window of a walk-forward analysis. */
export interface WalkForwardSplit {
	split: number;
	period_start: string;
	period_end: string;
	metrics: BacktestMetrics;
}

/**
 * Forward-test payload, returned on the standard `Backtest.result` when the
 * run was created with `params.mode = "forward"`. Extends `BacktestResult`
 * (trades, equity_curve, metrics, period) with promotion analysis.
 */
export interface ForwardReport extends BacktestResult {
	promotion: Promotion;
	rationale: string;
	/** In-sample (training split) metrics. */
	baseline: BacktestMetrics;
	/** Out-of-sample (test split) metrics. */
	forward: BacktestMetrics;
	/** Per-metric forward − baseline deltas. */
	drift: Partial<BacktestMetrics>;
	monte_carlo: MonteCarloReport;
	walk_forward: WalkForwardSplit[];
}

/** Full forward-test record (GET /backtests/{id} for a forward run). */
export interface ForwardTest extends Omit<Backtest, 'result'> {
	result?: ForwardReport | null;
}

// --- Discovery -----------------------------------------------------------------

export type DiscoveryStatus = 'queued' | 'running' | 'done' | 'error' | string;

/** Which side of a turning point the engine identified. */
export type DiscoveryEventKind = 'bought' | 'sold';

/** A single self-identified reason attached to a turning point. */
export interface DiscoveryReason {
	code: string;
	label: string;
	detail: string;
}

/** A significant turning point the engine found in the replayed history. */
export interface DiscoveryEvent {
	ts: string;
	kind: DiscoveryEventKind;
	price: number;
	forward_move_pct: number;
	forward_move_atr: number;
	reasons: DiscoveryReason[];
}

/**
 * Aggregated, validated reason statistics across all buy (or sell) events.
 *
 * The backend now cross-validates each reason on a held-out out-of-sample (OOS)
 * split: it reports the in-sample lift over the baseline forward move, the
 * t-statistic of the effect, the OOS lift, and a `holds_up` flag set when the
 * edge survives out-of-sample.
 */
export interface DiscoveryReasonStat {
	code: string;
	label: string;
	count: number;
	pct_of_events: number;
	avg_forward_move_pct: number;
	/** Mean forward move across all events on this side (the comparison baseline). */
	baseline_move_pct: number;
	/** In-sample edge: avg_forward_move_pct − baseline_move_pct (or a ratio). */
	lift: number;
	/** Significance of the in-sample effect. */
	t_stat: number;
	/** Number of events backing the out-of-sample estimate. */
	oos_count: number;
	/** Out-of-sample mean forward move for this reason. */
	oos_avg_move_pct: number;
	/** Out-of-sample edge over the baseline. */
	oos_lift: number;
	/** True when the edge survives out-of-sample validation. */
	holds_up: boolean;
}

/** A single condition within a promotable rule (e.g. `rsi14 < 35`). */
export interface RuleCondition {
	feature: string;
	op: string;
	threshold: number;
}

/**
 * A concrete, promotable trading rule the engine distilled from a validated
 * reason. It can be promoted into a live `custom_rule` scan.
 */
export interface SuggestedRule {
	name: string;
	direction: Exclude<Direction, 'NEUTRAL'>;
	conditions: RuleCondition[];
	/** Reason code this rule was derived from. */
	source_reason: string;
	in_sample_lift: number;
	oos_lift: number;
}

/** Full report payload of a finished discovery run. */
export interface DiscoveryReport {
	symbol: string;
	timeframe: string;
	trade_style: string;
	period_start: string;
	period_end: string;
	n_bars: number;
	n_events: number;
	n_bought: number;
	n_sold: number;
	events: DiscoveryEvent[];
	buy_reasons: DiscoveryReasonStat[];
	sell_reasons: DiscoveryReasonStat[];
	/** Mean forward move across all buy events (baseline for buy-reason lift). */
	baseline_buy_move: number;
	/** Mean forward move across all sell events (baseline for sell-reason lift). */
	baseline_sell_move: number;
	/** Fraction of events held out for out-of-sample validation (0..1). */
	validated_split: number;
	/** Promotable rules distilled from the validated reasons. */
	suggested_rules: SuggestedRule[];
}

/** Summary row for the "past discoveries" list (GET /discovery). */
export interface DiscoverySummary {
	discovery_id: string;
	symbol: string;
	timeframe: string;
	status: DiscoveryStatus;
	metrics?: Record<string, number> | null;
	params: Record<string, unknown>;
	created_at: string;
}

/** Full discovery record (GET /discovery/{id}), polled until status is done/error. */
export interface Discovery {
	discovery_id: string;
	symbol: string;
	timeframe: string;
	status: DiscoveryStatus;
	params: Record<string, unknown>;
	metrics?: Record<string, number> | null;
	report?: DiscoveryReport | null;
	error?: string | null;
	created_at: string;
	finished_at?: string | null;
}

export interface DiscoveriesResponse {
	items: DiscoverySummary[];
}

// --- Alerts --------------------------------------------------------------------

/** Delivery channel an alert rule routes matched signals through. */
export type AlertChannel = 'log' | 'webhook' | 'email' | string;

/** A user-defined alerting rule (GET /alerts/rules). */
export interface AlertRule {
	id: string;
	name: string;
	enabled: boolean;
	scanner_ids: string[];
	symbols: string[];
	sides: Side[];
	classifications: string[];
	min_score: number;
	channel: AlertChannel;
	target: string;
	cooldown_seconds: number;
	created_at: string;
}

export interface AlertRulesResponse {
	items: AlertRule[];
}

/** A fired alert (GET /alerts/events). */
export interface AlertEvent {
	id: string;
	rule_id: string;
	signal_id: string;
	symbol: string;
	side: Side;
	scanner_id: string;
	classification: string;
	score: number;
	channel: AlertChannel;
	delivered: boolean;
	error?: string | null;
	message: string;
	created_at: string;
}

export interface AlertEventsResponse {
	items: AlertEvent[];
}

// --- ML models ---------------------------------------------------------------

/** Model lifecycle/quality status. `training` is non-terminal; the rest are. */
export type ModelStatus = 'training' | 'reliable' | 'experimental' | 'error' | string;

/** A single calibration bucket: predicted probability vs observed frequency. */
export interface CalibrationPoint {
	predicted: number;
	actual: number;
}

/** Full evaluation report produced by a trained model (GET /ml/models/{id}). */
export interface ModelReport {
	scanner_id: string;
	n_samples: number;
	horizon: number;
	train_accuracy: number;
	test_accuracy: number;
	auc: number;
	brier: number;
	base_rate: number;
	feature_importance: Record<string, number>;
	calibration: CalibrationPoint[];
	reliable: boolean;
	symbol: string;
	timeframe: string;
}

/** Summary row for the "past models" list (GET /ml/models). */
export interface MlModelSummary {
	model_id: string;
	name: string;
	version: string;
	status: ModelStatus;
	metrics?: Record<string, number> | null;
	created_at: string;
}

/** Full model record (GET /ml/models/{id}), polled until status leaves `training`. */
export interface MlModel {
	model_id: string;
	name: string;
	version: string;
	status: ModelStatus;
	report?: ModelReport | null;
	created_at: string;
}

export interface MlModelsResponse {
	items: MlModelSummary[];
}

// --- ML Lab: self-learning ---------------------------------------------------

/** A single feature's mutual-information ranking against the forward label. */
export interface FeatureRanking {
	feature: string;
	mutual_information: number;
	/** Information gain expressed as a percentage of label entropy. */
	information_gain_pct: number;
}

/** Mutual-information feature report (GET /ml/feature-info). */
export interface FeatureInfoReport {
	label_entropy: number;
	base_rate: number;
	n_samples: number;
	rankings: FeatureRanking[];
	/** Highly-correlated feature pairs: [featureA, featureB, redundancyScore]. */
	redundant_pairs: [string, string, number][];
}

/** A single detected lookahead leak. */
export interface LeakProbe {
	feature: string;
	detail?: string;
	abs_diff?: number;
	[key: string]: unknown;
}

/** Leakage / lookahead audit report (GET /ml/leakage-audit). */
export interface LeakageAuditReport {
	clean: boolean;
	summary: string;
	n_probes: number;
	features_checked: number;
	leaks: LeakProbe[];
	max_abs_diff: number;
}

/** Calibrator quality stats (probability calibration). */
export interface CalibratorReport {
	n_samples: number;
	base_rate: number;
	brier_raw: number;
	brier_calibrated: number;
	improved: boolean;
}

/** Meta-labeling model report (secondary filter over a primary model). */
export interface MetaReport {
	primary_win_rate: number;
	meta_cv_auc: number;
	meta_precision_at_threshold: number;
	take_fraction: number;
	lift_vs_primary: number;
	fitted: boolean;
}

/** A single rule discovered by the rule miner. */
export interface MinedRule {
	description: string;
	train_hits: number;
	train_mean_return: number;
	valid_mean_return: number;
	holds_up: boolean;
}

/**
 * Generic self-learning job record. These jobs follow the same create→poll
 * lifecycle as `MlModel`: created with a `model_id`, polled via
 * `GET /ml/models/{id}` until `status` leaves `training`, then the relevant
 * report block is populated.
 */
export interface MlAdvancedReport {
	calibrator?: CalibratorReport | null;
	meta?: MetaReport | null;
	mined_rules?: MinedRule[] | null;
}

/** Full self-learning job record (calibrate / meta / mine). */
export interface MlAdvancedJob {
	model_id: string;
	name: string;
	version: string;
	status: ModelStatus;
	report?: MlAdvancedReport | null;
	created_at: string;
}
