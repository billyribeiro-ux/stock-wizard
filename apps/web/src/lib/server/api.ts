/**
 * Server-only FastAPI client.
 *
 * This module lives in `$lib/server` so SvelteKit guarantees it can never be
 * imported into browser code. It is the single seam through which the
 * SvelteKit server talks to the Python FastAPI backend. The internal token and
 * base URL are read from `$env/dynamic/private` and never leave the server.
 *
 * Remote functions (`*.remote.ts`) call into this module; the browser only ever
 * sees the remote-function HTTP endpoints SvelteKit generates, never FastAPI.
 */
import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type {
	AlertEventsResponse,
	AlertRulesResponse,
	Backtest,
	BacktestsResponse,
	DiscoveriesResponse,
	Discovery,
	FeatureInfoReport,
	HealthResponse,
	LeakageAuditReport,
	MlAdvancedJob,
	MlModel,
	MlModelsResponse,
	ReportSpec,
	RuleCondition,
	ScanRun,
	Scanner,
	ScannerResult,
	ScannerResultsResponse,
	SignalPacket,
	SignalsResponse,
	Vendor
} from '$lib/types';

function baseUrl(): string {
	const url = env.API_BASE_URL ?? 'http://localhost:8000';
	return url.replace(/\/+$/, '');
}

interface RequestOptions {
	method?: string;
	body?: unknown;
	query?: Record<string, string | number | undefined | null>;
	/** abort signal so live streams can be torn down */
	signal?: AbortSignal;
	headers?: Record<string, string>;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
	const url = new URL(`${baseUrl()}${path}`);
	if (query) {
		for (const [key, value] of Object.entries(query)) {
			if (value !== undefined && value !== null && value !== '') {
				url.searchParams.set(key, String(value));
			}
		}
	}
	return url.toString();
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
	const headers: Record<string, string> = {
		accept: 'application/json',
		...extra
	};
	const token = env.INTERNAL_API_TOKEN;
	if (token) {
		headers['authorization'] = `Bearer ${token}`;
		headers['x-internal-token'] = token;
	}
	return headers;
}

/** Perform a raw request, returning the `Response` for callers that need streaming or files. */
export async function rawRequest(path: string, options: RequestOptions = {}): Promise<Response> {
	const { method = 'GET', body, query, signal, headers } = options;
	const init: RequestInit = {
		method,
		headers: authHeaders(headers),
		signal
	};
	if (body !== undefined) {
		init.headers = { ...init.headers, 'content-type': 'application/json' };
		init.body = JSON.stringify(body);
	}
	return fetch(buildUrl(path, query), init);
}

/** Perform a JSON request and decode the body, surfacing backend errors as SvelteKit errors. */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	let response: Response;
	try {
		response = await rawRequest(path, options);
	} catch (cause) {
		throw error(502, {
			message: `Unable to reach trading backend: ${(cause as Error).message}`,
			code: 'BACKEND_UNREACHABLE'
		});
	}

	if (!response.ok) {
		let detail = response.statusText;
		try {
			const payload = (await response.json()) as { detail?: string; message?: string };
			detail = payload.detail ?? payload.message ?? detail;
		} catch {
			// non-JSON error body; keep the status text
		}
		throw error(response.status, {
			message: detail || `Backend request failed (${response.status})`,
			code: 'BACKEND_ERROR'
		});
	}

	if (response.status === 204) {
		return undefined as T;
	}

	return (await response.json()) as T;
}

// --- Health -----------------------------------------------------------------

export function getHealth(): Promise<HealthResponse> {
	return request<HealthResponse>('/health');
}

// --- Scanners & scans --------------------------------------------------------

export function listScanners(): Promise<Scanner[]> {
	return request<Scanner[]>('/scanners');
}

export interface StartScanPayload {
	scanner_id: string;
	symbols: string[];
	timeframe: string;
	history: string;
	params: Record<string, unknown>;
}

export function startScan(payload: StartScanPayload): Promise<{ run_id: string }> {
	return request<{ run_id: string }>('/scans', { method: 'POST', body: payload });
}

export function getScan(runId: string): Promise<ScanRun> {
	return request<ScanRun>(`/scans/${encodeURIComponent(runId)}`);
}

export function getScanResults(runId: string): Promise<ScannerResultsResponse> {
	return request<ScannerResultsResponse>(`/scans/${encodeURIComponent(runId)}/results`);
}

export function getResult(id: string): Promise<ScannerResult> {
	return request<ScannerResult>(`/results/${encodeURIComponent(id)}`);
}

export function getSignals(runId?: string): Promise<SignalsResponse> {
	return request<SignalsResponse>('/signals', { query: { run_id: runId } });
}

// --- Backtests ---------------------------------------------------------------

export interface CreateBacktestPayload {
	scanner_id: string;
	symbol: string;
	timeframe: string;
	history: string;
	params: Record<string, unknown>;
}

export function createBacktest(
	payload: CreateBacktestPayload
): Promise<{ backtest_id: string; enqueued: boolean }> {
	return request<{ backtest_id: string; enqueued: boolean }>('/backtests', {
		method: 'POST',
		body: payload
	});
}

export function listBacktests(): Promise<BacktestsResponse> {
	return request<BacktestsResponse>('/backtests');
}

export function getBacktest(id: string): Promise<Backtest> {
	return request<Backtest>(`/backtests/${encodeURIComponent(id)}`);
}

// --- Discovery -----------------------------------------------------------------

export interface CreateDiscoveryPayload {
	symbol: string;
	timeframe: string;
	history: string;
	swing_k?: number;
	min_move_atr?: number;
}

export function createDiscovery(
	payload: CreateDiscoveryPayload
): Promise<{ discovery_id: string; enqueued: boolean }> {
	return request<{ discovery_id: string; enqueued: boolean }>('/discovery', {
		method: 'POST',
		body: payload
	});
}

export function listDiscoveries(): Promise<DiscoveriesResponse> {
	return request<DiscoveriesResponse>('/discovery');
}

export function getDiscovery(id: string): Promise<Discovery> {
	return request<Discovery>(`/discovery/${encodeURIComponent(id)}`);
}

/**
 * Fetch a discovery export (CSV/PDF) from the backend, returning the raw
 * `Response` so the SvelteKit proxy endpoint can stream the body and forward
 * the content-type / content-disposition headers to the browser.
 */
export async function exportDiscovery(id: string, fmt: 'csv' | 'pdf'): Promise<Response> {
	try {
		return await rawRequest(`/exports/discovery/${encodeURIComponent(id)}`, {
			query: { fmt },
			headers: { accept: fmt === 'pdf' ? 'application/pdf' : 'text/csv' }
		});
	} catch (cause) {
		throw error(502, {
			message: `Unable to reach trading backend: ${(cause as Error).message}`,
			code: 'BACKEND_UNREACHABLE'
		});
	}
}

/**
 * Promote a validated discovery rule into a live scan. POSTs to `/scans` with
 * the built-in `custom_rule` scanner, passing the rule's direction, conditions
 * and name as params. Returns the new `run_id`.
 */
export interface PromoteRulePayload {
	symbol: string;
	timeframe: string;
	direction: 'LONG' | 'SHORT';
	conditions: RuleCondition[];
	name: string;
}

export function promoteRule(payload: PromoteRulePayload): Promise<{ run_id: string }> {
	const { symbol, timeframe, direction, conditions, name } = payload;
	return request<{ run_id: string }>('/scans', {
		method: 'POST',
		body: {
			scanner_id: 'custom_rule',
			symbols: [symbol],
			timeframe,
			params: { direction, conditions, name }
		}
	});
}

// --- ML models ---------------------------------------------------------------

export interface TrainModelPayload {
	scanner_id?: string;
	symbol: string;
	timeframe: string;
	history: string;
	horizon: number;
}

export function trainModel(
	payload: TrainModelPayload
): Promise<{ model_id: string; enqueued: boolean }> {
	return request<{ model_id: string; enqueued: boolean }>('/ml/train', {
		method: 'POST',
		body: payload
	});
}

export function listModels(): Promise<MlModelsResponse> {
	return request<MlModelsResponse>('/ml/models');
}

export function getModel(id: string): Promise<MlModel> {
	return request<MlModel>(`/ml/models/${encodeURIComponent(id)}`);
}

// --- ML Lab: self-learning ---------------------------------------------------

export interface FeatureInfoQuery {
	symbol: string;
	timeframe: string;
	history: string;
	horizon: number;
}

/** Mutual-information feature ranking + redundancy report. */
export function getFeatureInfo(params: FeatureInfoQuery): Promise<FeatureInfoReport> {
	return request<FeatureInfoReport>('/ml/feature-info', { query: { ...params } });
}

export interface LeakageAuditQuery {
	symbol: string;
	timeframe: string;
	history: string;
}

/** Lookahead / leakage audit report. */
export function getLeakageAudit(params: LeakageAuditQuery): Promise<LeakageAuditReport> {
	return request<LeakageAuditReport>('/ml/leakage-audit', { query: { ...params } });
}

export interface AdvancedJobPayload {
	scanner_id?: string;
	symbol: string;
	timeframe: string;
	history: string;
	horizon: number;
}

/** Kick off probability calibration; poll `getAdvancedJob(model_id)`. */
export function calibrateModel(payload: AdvancedJobPayload): Promise<{ model_id: string }> {
	return request<{ model_id: string }>('/ml/calibrate', { method: 'POST', body: payload });
}

/** Kick off meta-labeling training; poll `getAdvancedJob(model_id)`. */
export function trainMeta(payload: AdvancedJobPayload): Promise<{ model_id: string }> {
	return request<{ model_id: string }>('/ml/meta', { method: 'POST', body: payload });
}

export interface MineRulesPayload {
	symbol: string;
	timeframe: string;
	history: string;
	horizon: number;
}

/** Kick off rule mining; poll `getAdvancedJob(model_id)`. */
export function mineRules(payload: MineRulesPayload): Promise<{ model_id: string }> {
	return request<{ model_id: string }>('/ml/mine', { method: 'POST', body: payload });
}

/**
 * Poll a self-learning job (calibrate / meta / mine). Reuses the shared
 * `/ml/models/{id}` lifecycle endpoint; the populated `report` block depends on
 * which job kind was started.
 */
export function getAdvancedJob(id: string): Promise<MlAdvancedJob> {
	return request<MlAdvancedJob>(`/ml/models/${encodeURIComponent(id)}`);
}

// --- Vendor API keys ---------------------------------------------------------

export function listVendors(): Promise<Vendor[]> {
	return request<Vendor[]>('/vendors');
}

export interface CreateVendorKeyPayload {
	vendor: string;
	label: string;
	api_key: string;
	scopes: string[];
}

export function createVendorKey(payload: CreateVendorKeyPayload): Promise<{ id: string }> {
	return request<{ id: string }>('/vendors/keys', { method: 'POST', body: payload });
}

export function setVendorKeyEnabled(
	id: string,
	enabled: boolean
): Promise<{ id: string; enabled: boolean }> {
	return request<{ id: string; enabled: boolean }>(`/vendors/keys/${encodeURIComponent(id)}`, {
		method: 'PATCH',
		body: { enabled }
	});
}

export function deleteVendorKey(id: string): Promise<void> {
	return request<void>(`/vendors/keys/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

// --- Alerts --------------------------------------------------------------------

export function listAlertRules(): Promise<AlertRulesResponse> {
	return request<AlertRulesResponse>('/alerts/rules');
}

export interface CreateAlertRulePayload {
	name: string;
	scanner_ids: string[];
	symbols: string[];
	sides: string[];
	classifications: string[];
	min_score: number;
	channel: string;
	target: string;
	cooldown_seconds: number;
}

export function createAlertRule(payload: CreateAlertRulePayload): Promise<{ id: string }> {
	return request<{ id: string }>('/alerts/rules', { method: 'POST', body: payload });
}

export function setAlertRuleEnabled(
	id: string,
	enabled: boolean
): Promise<{ id: string; enabled: boolean }> {
	return request<{ id: string; enabled: boolean }>(`/alerts/rules/${encodeURIComponent(id)}`, {
		method: 'PATCH',
		body: { enabled }
	});
}

export function deleteAlertRule(id: string): Promise<void> {
	return request<void>(`/alerts/rules/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function listAlertEvents(): Promise<AlertEventsResponse> {
	return request<AlertEventsResponse>('/alerts/events');
}

// --- Exports -----------------------------------------------------------------

export function createExport(spec: ReportSpec): Promise<{ export_id: string }> {
	return request<{ export_id: string }>('/exports', { method: 'POST', body: spec });
}

// --- Live signals (SSE) ------------------------------------------------------

/**
 * Connect to the backend SSE signal stream for a run and yield each parsed
 * `SignalPacket`. Used by the `query.live` remote generator. Falls back to
 * polling `/signals` if the SSE endpoint is unavailable.
 */
export async function* streamSignals(
	runId: string,
	signal?: AbortSignal
): AsyncGenerator<SignalPacket> {
	let response: Response;
	try {
		response = await rawRequest('/stream/signals', {
			query: { run_id: runId },
			headers: { accept: 'text/event-stream' },
			signal
		});
	} catch {
		yield* pollSignals(runId, signal);
		return;
	}

	if (!response.ok || !response.body) {
		yield* pollSignals(runId, signal);
		return;
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	try {
		while (true) {
			const { value, done } = await reader.read();
			if (done) break;
			buffer += decoder.decode(value, { stream: true });

			// SSE frames are separated by a blank line
			let boundary: number;
			while ((boundary = buffer.indexOf('\n\n')) !== -1) {
				const frame = buffer.slice(0, boundary);
				buffer = buffer.slice(boundary + 2);
				const data = parseSseData(frame);
				if (data) {
					try {
						yield JSON.parse(data) as SignalPacket;
					} catch {
						// skip malformed frame
					}
				}
			}
		}
	} finally {
		await reader.cancel().catch(() => {});
	}
}

function parseSseData(frame: string): string | null {
	const lines = frame.split('\n');
	const dataLines = lines
		.filter((line) => line.startsWith('data:'))
		.map((line) => line.slice(5).trimStart());
	if (dataLines.length === 0) return null;
	return dataLines.join('\n');
}

/** Polling fallback: re-fetch `/signals` and emit any newly seen packets. */
async function* pollSignals(runId: string, signal?: AbortSignal): AsyncGenerator<SignalPacket> {
	const seen = new Set<string>();
	while (!signal?.aborted) {
		try {
			const { items } = await getSignals(runId);
			for (const item of items) {
				if (!seen.has(item.signal_id)) {
					seen.add(item.signal_id);
					yield item;
				}
			}
		} catch {
			// transient backend error; keep polling
		}
		await new Promise((resolve) => setTimeout(resolve, 2000));
	}
}
