import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { DiscoveriesResponse, Discovery } from '$lib/types';

const RunDiscoverySchema = v.object({
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	min_move_atr: v.pipe(v.number(), v.minValue(0.5), v.maxValue(5))
});

/**
 * Enqueue a discovery run. Returns the new `discovery_id`; the page then polls
 * `getDiscovery(id)` until the run reaches `done` or `error`.
 */
export const runDiscovery = command(
	RunDiscoverySchema,
	async (input): Promise<{ discovery_id: string }> => {
		const { discovery_id } = await api.createDiscovery(input);
		return { discovery_id };
	}
);

/** Full discovery record (polled until status is done/error). */
export const getDiscovery = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<Discovery> => {
		return api.getDiscovery(id);
	}
);

/** Past discoveries with status + key metrics. */
export const listDiscoveries = query(async (): Promise<DiscoveriesResponse> => {
	return api.listDiscoveries();
});

const PromoteRuleSchema = v.object({
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	direction: v.picklist(['LONG', 'SHORT']),
	name: v.pipe(v.string(), v.nonEmpty('Provide a rule name')),
	conditions: v.array(
		v.object({
			feature: v.pipe(v.string(), v.nonEmpty()),
			op: v.pipe(v.string(), v.nonEmpty()),
			threshold: v.number()
		})
	)
});

/**
 * Promote a validated discovery rule into a live `custom_rule` scan. Returns the
 * new `run_id`; the page links to `/results?run=<run_id>` on success.
 */
export const promoteRule = command(
	PromoteRuleSchema,
	async (input): Promise<{ run_id: string }> => {
		const { run_id } = await api.promoteRule(input);
		return { run_id };
	}
);
