import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { Scanner } from '$lib/types';

/** Catalogue of available scanners and their JSON-schema params. */
export const listScanners = query(async (): Promise<Scanner[]> => {
	return api.listScanners();
});

const RunScanSchema = v.object({
	scanner_id: v.pipe(v.string(), v.nonEmpty('Pick a scanner')),
	symbols: v.pipe(
		v.array(v.pipe(v.string(), v.nonEmpty())),
		v.minLength(1, 'Provide at least one symbol')
	),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	params: v.record(v.string(), v.unknown())
});

/**
 * Kick off a scan. Returns the new `run_id`; the page navigates to
 * `/results?run=<run_id>` on the client after this resolves.
 */
export const runScan = command(RunScanSchema, async (input): Promise<{ run_id: string }> => {
	return api.startScan(input);
});
