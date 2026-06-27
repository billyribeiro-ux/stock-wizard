import * as v from 'valibot';
import { query } from '$app/server';
import * as api from '$lib/server/api';
import type { Backtest, BacktestSummary } from '$lib/types';

/** Finished backtests that can be replayed trade-by-trade. */
export const listReplayableBacktests = query(async (): Promise<BacktestSummary[]> => {
	const { items } = await api.listBacktests();
	return items.filter((item) => item.status?.toLowerCase() === 'done');
});

/** Full backtest record, including trades and the equity curve. */
export const getBacktest = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<Backtest> => {
		return api.getBacktest(id);
	}
);
