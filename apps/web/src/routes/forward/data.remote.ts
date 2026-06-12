import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { ForwardTest, BacktestsResponse, Scanner } from '$lib/types';

/** Scanner ids that the backtest/forward engine can replay. */
const BACKTESTABLE_SCANNERS = ['mtf_structure', 'volume_profile_poc'];

/** Catalogue of scanners filtered to those that support forward testing. */
export const listForwardScanners = query(async (): Promise<Scanner[]> => {
	const scanners = await api.listScanners();
	return scanners.filter((s) => BACKTESTABLE_SCANNERS.includes(s.scanner_id));
});

const CreateForwardTestSchema = v.object({
	scanner_id: v.pipe(v.string(), v.nonEmpty('Pick a scanner')),
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	split_frac: v.pipe(v.number(), v.minValue(0.4), v.maxValue(0.8))
});

/**
 * Enqueue a forward test. Reuses the backtest engine with `params.mode =
 * "forward"`. Returns the new `backtest_id`; the page then polls
 * `getForwardTest(id)` until the run reaches `done` or `error`.
 */
export const createForwardTest = command(
	CreateForwardTestSchema,
	async (input): Promise<{ backtest_id: string }> => {
		const { backtest_id } = await api.createBacktest({
			scanner_id: input.scanner_id,
			symbol: input.symbol,
			timeframe: input.timeframe,
			history: input.history,
			params: { mode: 'forward', split_frac: input.split_frac }
		});
		return { backtest_id };
	}
);

/** Full forward-test record (polled until status is done/error). */
export const getForwardTest = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<ForwardTest> => {
		return api.getBacktest(id) as Promise<ForwardTest>;
	}
);

/** Past forward tests with status + key metrics. */
export const listForwardTests = query(async (): Promise<BacktestsResponse> => {
	return api.listBacktests();
});
