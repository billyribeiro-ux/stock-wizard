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
	Backtest,
	BacktestsResponse,
	HealthResponse,
	ReportSpec,
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
