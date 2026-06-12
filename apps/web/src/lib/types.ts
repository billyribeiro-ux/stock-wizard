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

export interface Scanner {
	scanner_id: string;
	name: string;
	description: string;
	params_schema: JsonSchema;
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
	last_used_at?: string | null;
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
