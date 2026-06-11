import { query } from '$app/server';
import * as api from '$lib/server/api';
import type { HealthResponse, SignalsResponse } from '$lib/types';

/** Backend health + per-symbol data freshness for the Command Center. */
export const getHealth = query(async (): Promise<HealthResponse> => {
	return api.getHealth();
});

/** Recent signals across all runs (no run filter) for the dashboard feed. */
export const getRecentSignals = query(async (): Promise<SignalsResponse> => {
	return api.getSignals();
});
