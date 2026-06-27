import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { AlertEvent, AlertRule, Scanner } from '$lib/types';

/** Catalogue of scanners an alert rule can subscribe to. */
export const listScanners = query(async (): Promise<Scanner[]> => {
	return api.listScanners();
});

/** Configured alert rules. */
export const listRules = query(async (): Promise<AlertRule[]> => {
	const { items } = await api.listAlertRules();
	return items;
});

/** Fired-alert history, newest first per the backend. */
export const listEvents = query(async (): Promise<AlertEvent[]> => {
	const { items } = await api.listAlertEvents();
	return items;
});

const CreateRuleSchema = v.object({
	name: v.pipe(v.string(), v.nonEmpty('Give the rule a name')),
	scanner_ids: v.array(v.string()),
	symbols: v.array(v.pipe(v.string(), v.nonEmpty())),
	sides: v.pipe(
		v.array(v.picklist(['LONG', 'SHORT', 'NEUTRAL'])),
		v.minLength(1, 'Pick at least one side')
	),
	classifications: v.optional(v.array(v.string()), []),
	min_score: v.pipe(v.number(), v.minValue(0), v.maxValue(1)),
	channel: v.picklist(['log', 'webhook', 'email']),
	target: v.string(),
	cooldown_seconds: v.pipe(v.number(), v.minValue(0))
});

/** Create an alert rule and refresh the rule list in the same flight. */
export const createRule = command(CreateRuleSchema, async (input): Promise<{ id: string }> => {
	const { id } = await api.createAlertRule({
		...input,
		classifications: input.classifications ?? []
	});
	void listRules().refresh();
	return { id };
});

const ToggleSchema = v.object({
	id: v.pipe(v.string(), v.nonEmpty()),
	enabled: v.boolean()
});

/** Enable or disable a rule. */
export const setRuleEnabled = command(ToggleSchema, async ({ id, enabled }) => {
	const result = await api.setAlertRuleEnabled(id, enabled);
	void listRules().refresh();
	return result;
});

/** Remove a rule entirely. */
export const removeRule = command(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<{ id: string }> => {
		await api.deleteAlertRule(id);
		void listRules().refresh();
		return { id };
	}
);
