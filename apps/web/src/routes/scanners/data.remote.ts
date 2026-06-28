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

const RunEnsembleSchema = v.object({
	scanners: v.pipe(
		v.array(v.pipe(v.string(), v.nonEmpty())),
		v.minLength(2, 'Pick at least two scanners to fuse')
	),
	symbols: v.pipe(
		v.array(v.pipe(v.string(), v.nonEmpty())),
		v.minLength(1, 'Provide at least one symbol')
	),
	timeframe: v.optional(v.string(), '1d'),
	history: v.optional(v.string(), '1y')
});

/** Run a regime-conditional ensemble scan — fuses scanners weighted by their current-regime
 * out-of-sample edge into one consensus signal per symbol. */
export const runEnsembleScan = command(
	RunEnsembleSchema,
	async (input): Promise<{ run_id: string; scanners: string[] }> => {
		return api.startEnsembleScan(input);
	}
);
