import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type {
	FeatureInfoReport,
	LeakageAuditReport,
	MlAdvancedJob,
	Scanner
} from '$lib/types';

/** Full scanner catalogue, used to populate the scanner_id pickers. */
export const listScanners = query(async (): Promise<Scanner[]> => {
	return api.listScanners();
});

const FeatureInfoSchema = v.object({
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	horizon: v.pipe(v.number(), v.integer(), v.minValue(1, 'Horizon must be at least 1'))
});

/** Mutual-information feature ranking + redundancy report. */
export const getFeatureInfo = query(
	FeatureInfoSchema,
	async (input): Promise<FeatureInfoReport> => {
		return api.getFeatureInfo(input);
	}
);

const LeakageAuditSchema = v.object({
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty())
});

/** Lookahead / leakage audit report. */
export const getLeakageAudit = query(
	LeakageAuditSchema,
	async (input): Promise<LeakageAuditReport> => {
		return api.getLeakageAudit(input);
	}
);

const AdvancedJobSchema = v.object({
	scanner_id: v.pipe(v.string(), v.nonEmpty('Pick a scanner')),
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	horizon: v.pipe(v.number(), v.integer(), v.minValue(1, 'Horizon must be at least 1'))
});

/** Start a calibration job; poll `getAdvancedJob(model_id)` until done. */
export const calibrateModel = command(
	AdvancedJobSchema,
	async (input): Promise<{ model_id: string }> => {
		const { model_id } = await api.calibrateModel(input);
		return { model_id };
	}
);

/** Start a meta-labeling job; poll `getAdvancedJob(model_id)` until done. */
export const trainMeta = command(
	AdvancedJobSchema,
	async (input): Promise<{ model_id: string }> => {
		const { model_id } = await api.trainMeta(input);
		return { model_id };
	}
);

const MineRulesSchema = v.object({
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	horizon: v.pipe(v.number(), v.integer(), v.minValue(1, 'Horizon must be at least 1'))
});

/** Start a rule-mining job; poll `getAdvancedJob(model_id)` until done. */
export const mineRules = command(
	MineRulesSchema,
	async (input): Promise<{ model_id: string }> => {
		const { model_id } = await api.mineRules(input);
		return { model_id };
	}
);

/** Poll a self-learning job (calibrate / meta / mine) until status leaves `training`. */
export const getAdvancedJob = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<MlAdvancedJob> => {
		return api.getAdvancedJob(id);
	}
);
