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
