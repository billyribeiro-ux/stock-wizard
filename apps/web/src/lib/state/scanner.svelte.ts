/**
 * Shared reactive state for the Scanner Builder form.
 *
 * We export a single object whose properties are mutated (never the binding
 * itself reassigned), which is the supported pattern for sharing `$state`
 * across modules in Svelte 5.
 */
import type { Scanner } from '$lib/types';

export interface ScannerBuilderState {
	scannerId: string;
	symbolsInput: string;
	timeframe: string;
	history: string;
	params: Record<string, unknown>;
}

export const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'] as const;
export const HISTORY_WINDOWS = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y'] as const;

export const builder: ScannerBuilderState = $state({
	scannerId: '',
	symbolsInput: 'SPY',
	timeframe: '1d',
	history: '1y',
	params: {}
});

/** Parse the comma/space separated symbols box into a clean, de-duped, upper-cased list. */
export function parseSymbols(input: string): string[] {
	const out: string[] = [];
	for (const raw of input.split(/[\s,]+/)) {
		const symbol = raw.trim().toUpperCase();
		if (symbol && !out.includes(symbol)) out.push(symbol);
	}
	return out;
}

/** Seed `params` with the defaults declared in a scanner's JSON schema. */
export function selectScanner(scanner: Scanner): void {
	builder.scannerId = scanner.scanner_id;
	const next: Record<string, unknown> = {};
	const props = scanner.params_schema?.properties ?? {};
	for (const [key, schema] of Object.entries(props)) {
		if (schema.default !== undefined) {
			next[key] = schema.default;
		} else if (schema.type === 'boolean') {
			next[key] = false;
		} else if (schema.type === 'number' || schema.type === 'integer') {
			next[key] = schema.minimum ?? 0;
		} else if (schema.enum && schema.enum.length > 0) {
			next[key] = schema.enum[0];
		} else {
			next[key] = '';
		}
	}
	builder.params = next;
}

export function setParam(key: string, value: unknown): void {
	builder.params[key] = value;
}

export function resetBuilder(): void {
	builder.scannerId = '';
	builder.symbolsInput = 'SPY';
	builder.timeframe = '1d';
	builder.history = '1y';
	builder.params = {};
}
