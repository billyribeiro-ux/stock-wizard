import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { EdgeWeight } from '$lib/server/api';
import type { Scanner } from '$lib/types';

/** Scanner catalogue (for the multi-select). */
export const listScanners = query(async (): Promise<Scanner[]> => {
	return api.listScanners();
});

/** Persisted per-scanner OOS edge weights (global + per-regime), to show which scanners are
 * proven in which regime. */
export const listEdgeWeights = query(async (): Promise<{ items: EdgeWeight[] }> => {
	return api.listEdgeWeights();
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

/** Run a regime-conditional ensemble scan and return the new run id. */
export const runEnsembleScan = command(
	RunEnsembleSchema,
	async (input): Promise<{ run_id: string; scanners: string[] }> => {
		return api.startEnsembleScan(input);
	}
);
