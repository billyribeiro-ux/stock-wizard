import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { Scanner, ScanRun, ScannerResultsResponse } from '$lib/types';

/** Catalogue of available scanners (to pick which one to scan the watchlist with). */
export const listScanners = query(async (): Promise<Scanner[]> => {
	return api.listScanners();
});

const ScanWatchlistSchema = v.object({
	scanner_id: v.pipe(v.string(), v.nonEmpty('Pick a scanner')),
	symbols: v.pipe(
		v.array(v.pipe(v.string(), v.nonEmpty())),
		v.minLength(1, 'Add at least one symbol')
	),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty())
});

/**
 * Scan the whole watchlist with one scanner. Returns the new `run_id`; the page
 * then polls `getScan(id)` until finished, then loads `getScanResults(id)`.
 */
export const scanWatchlist = command(
	ScanWatchlistSchema,
	async (input): Promise<{ run_id: string }> => {
		return api.startScan({ ...input, params: {} });
	}
);

/** Scan run status (polled until finished/error). */
export const getScan = query(v.pipe(v.string(), v.nonEmpty()), async (id): Promise<ScanRun> => {
	return api.getScan(id);
});

/** Results for a finished scan run. */
export const getScanResults = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<ScannerResultsResponse> => {
		return api.getScanResults(id);
	}
);
