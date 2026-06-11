import * as v from 'valibot';
import { query } from '$app/server';
import * as api from '$lib/server/api';
import type { ScanRun, ScannerResult, ScannerResultsResponse, SignalPacket } from '$lib/types';

/** Status of a scan run (polled by the results page until finished). */
export const getRun = query(v.pipe(v.string(), v.nonEmpty()), async (runId): Promise<ScanRun> => {
	return api.getScan(runId);
});

/** Materialised results for a run. */
export const getResults = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (runId): Promise<ScannerResultsResponse> => {
		return api.getScanResults(runId);
	}
);

/** A single result with its embedded evidence packet, for the evidence viewer. */
export const getResult = query(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<ScannerResult> => {
		return api.getResult(id);
	}
);

/**
 * Live stream of signals for a run. Thin wrapper over the server-only SSE
 * client — yields each new `SignalPacket` as it arrives so the results page's
 * side panel updates in real time. SvelteKit keeps the underlying stream
 * connected only while it is in active use in a component.
 */
export const liveSignals = query.live(
	v.pipe(v.string(), v.nonEmpty()),
	async function* (runId): AsyncGenerator<SignalPacket> {
		yield* api.streamSignals(runId);
	}
);
