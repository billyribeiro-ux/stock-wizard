import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { Backtest, BacktestsResponse, Scanner } from '$lib/types';

/** Scanner ids that the backtest engine can replay. */
const BACKTESTABLE_SCANNERS = ['mtf_structure', 'volume_profile_poc'];

/** Catalogue of scanners filtered to those that support backtesting. */
export const listBacktestableScanners = query(async (): Promise<Scanner[]> => {
	const scanners = await api.listScanners();
	return scanners.filter((s) => BACKTESTABLE_SCANNERS.includes(s.scanner_id));
});

const CreateBacktestSchema = v.object({
	scanner_id: v.pipe(v.string(), v.nonEmpty('Pick a scanner')),
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	params: v.record(v.string(), v.unknown())
});

/**
 * Enqueue a backtest. Returns the new `backtest_id`; the page then polls
 * `getBacktest(id)` until the run reaches `done` or `error`.
 */
export const createBacktest = command(
	CreateBacktestSchema,
	async (input): Promise<{ backtest_id: string }> => {
		const { backtest_id } = await api.createBacktest(input);
		return { backtest_id };
	}
);

/** Full backtest record (polled until status is done/error). */
export const getBacktest = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<Backtest> => {
		return api.getBacktest(id);
	}
);

/** Past backtests with status + key metrics. */
export const listBacktests = query(async (): Promise<BacktestsResponse> => {
	return api.listBacktests();
});
