import * as v from 'valibot';
import { command, query } from '$app/server';
import * as api from '$lib/server/api';
import type { ScannerResult } from '$lib/types';

const GAMMA_SCANNER_ID = 'spx_gamma_command';

const RunGammaSchema = v.object({
	underlying: v.pipe(v.string(), v.nonEmpty('Provide an underlying')),
	timeframe: v.pipe(v.string(), v.nonEmpty())
});

/**
 * Kick off a focused SPX gamma scan. POSTs /scans with the gamma scanner and a
 * single-symbol universe, then returns the new `run_id`. The page polls
 * `getGammaRun` until finished and loads `getGammaResults`.
 */
export const runGammaScan = command(RunGammaSchema, async (input): Promise<{ run_id: string }> => {
	return api.startScan({
		scanner_id: GAMMA_SCANNER_ID,
		symbols: [input.underlying.trim().toUpperCase()],
		timeframe: input.timeframe,
		history: '1d',
		params: {}
	});
});

/** Status of a gamma scan run (polled until finished). */
export const getGammaRun = query(v.pipe(v.string(), v.nonEmpty()), async (runId) => {
	return api.getScan(runId);
});

/** The single gamma result for a finished run. */
export const getGammaResult = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (runId): Promise<ScannerResult | null> => {
		const { items } = await api.getScanResults(runId);
		return items[0] ?? null;
	}
);
