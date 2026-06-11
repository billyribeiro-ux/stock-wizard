/**
 * Reactive wrapper around the `liveSignals` live query.
 *
 * The component owns the underlying live query (so SvelteKit keeps the stream
 * connected while mounted); this class accumulates the streamed packets into a
 * capped, newest-first buffer and tracks connection status for the "LIVE"
 * indicator.
 */
import type { SignalPacket } from '$lib/types';

export class SignalStream {
	#signals = $state<SignalPacket[]>([]);
	#connected = $state(false);
	#lastReceived = $state<number | null>(null);
	#limit: number;

	constructor(limit = 50) {
		this.#limit = limit;
	}

	get signals(): SignalPacket[] {
		return this.#signals;
	}

	get connected(): boolean {
		return this.#connected;
	}

	get count(): number {
		return this.#signals.length;
	}

	get lastReceived(): number | null {
		return this.#lastReceived;
	}

	setConnected(value: boolean): void {
		this.#connected = value;
	}

	/** Push a freshly streamed signal to the front of the buffer, de-duped by id. */
	push(signal: SignalPacket): void {
		if (this.#signals.some((existing) => existing.signal_id === signal.signal_id)) {
			return;
		}
		this.#signals = [signal, ...this.#signals].slice(0, this.#limit);
		this.#lastReceived = Date.now();
	}

	clear(): void {
		this.#signals = [];
		this.#lastReceived = null;
	}
}
