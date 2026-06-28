import * as v from 'valibot';
import { query, command } from '$app/server';
import * as api from '$lib/server/api';
import type { EdgeWeight } from '$lib/server/api';
import type { MlModel, MlModelsResponse } from '$lib/types';

const TrainModelSchema = v.object({
	scanner_id: v.optional(v.string()),
	symbol: v.pipe(v.string(), v.nonEmpty('Provide a symbol')),
	timeframe: v.pipe(v.string(), v.nonEmpty()),
	history: v.pipe(v.string(), v.nonEmpty()),
	horizon: v.pipe(v.number(), v.integer(), v.minValue(1, 'Horizon must be at least 1'))
});

/**
 * Enqueue a model training run. Returns the new `model_id`; the page then polls
 * `getModel(id)` until the status leaves `training`.
 */
export const trainModel = command(
	TrainModelSchema,
	async (input): Promise<{ model_id: string }> => {
		const { model_id } = await api.trainModel(input);
		return { model_id };
	}
);

/** Full model record (polled until status is not `training`). */
export const getModel = query(v.pipe(v.string(), v.nonEmpty()), async (id): Promise<MlModel> => {
	return api.getModel(id);
});

/** Past models with status + key metrics. */
export const listModels = query(async (): Promise<MlModelsResponse> => {
	return api.listModels();
});

/** Latest persisted walk-forward / roster edge weight per scanner. */
export const listEdgeWeights = query(async (): Promise<{ items: EdgeWeight[] }> => {
	return api.listEdgeWeights();
});

/** Kick off a background roster validation (forward-tests the scanner roster, persists
 * each scanner's blended out-of-sample edge weight). */
export const validateRoster = command(
	v.optional(
		v.object({
			symbols: v.optional(v.array(v.string())),
			history: v.optional(v.string())
		}),
		{}
	),
	async (input): Promise<{ status: string; roster: string[] }> => {
		return api.validateRoster(input ?? {});
	}
);
