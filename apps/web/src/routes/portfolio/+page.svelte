<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { scanWatchlist, getScan, getScanResults, listScanners } from './data.remote';
	import type { Scanner, ScanRun, ScannerResult } from '$lib/types';

	const TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d', '1w'] as const;
	const HISTORY_WINDOWS = ['1y', '2y', '5y', '10y'] as const;

	// --- Watchlist state -----------------------------------------------------
	let watchlist = $state<string[]>(['SPY', 'QQQ', 'IWM', 'AAPL', 'NVDA']);
	let newSymbol = $state('');

	// --- Scan config ---------------------------------------------------------
	let scannerId = $state('');
	let timeframe = $state('1d');
	let history = $state('1y');

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	// Active scan run id (drives polling + results panel).
	let activeRunId = $state<string | null>(null);

	function addSymbol(): void {
		const sym = newSymbol.trim().toUpperCase();
		if (!sym) return;
		if (!watchlist.includes(sym)) watchlist = [...watchlist, sym];
		newSymbol = '';
	}

	function removeSymbol(sym: string): void {
		watchlist = watchlist.filter((s) => s !== sym);
	}

	function isTerminal(status: string | undefined): boolean {
		const s = status?.toLowerCase();
		return s === 'finished' || s === 'error';
	}

	// Poll the active run until it finishes/errors. Reading the query's `current`
	// status re-runs the effect and stops the interval once terminal.
	$effect(() => {
		const id = activeRunId;
		if (!id) return;
		const status = getScan(id).current?.status;
		if (isTerminal(status)) return;
		const handle = setInterval(() => {
			getScan(id).refresh();
		}, 1500);
		return () => clearInterval(handle);
	});

	async function submit(scanners: Scanner[]): Promise<void> {
		errorMessage = null;
		const id = scannerId || scanners[0]?.scanner_id;
		if (!id) {
			errorMessage = 'No scanner available.';
			return;
		}
		if (watchlist.length === 0) {
			errorMessage = 'Add at least one symbol to the watchlist.';
			return;
		}

		submitting = true;
		try {
			const { run_id } = await scanWatchlist({
				scanner_id: id,
				symbols: watchlist,
				timeframe,
				history
			});
			activeRunId = run_id;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start scan.';
		} finally {
			submitting = false;
		}
	}

	function statusTone(status: string): string {
		const s = status?.toLowerCase();
		if (s === 'finished') return 'text-ok';
		if (s === 'error') return 'text-danger';
		return 'text-warn';
	}

	function directionTone(direction: string | undefined): string {
		if (direction === 'LONG') return 'text-long';
		if (direction === 'SHORT') return 'text-short';
		return 'text-neutral-signal';
	}

	function fmtLevels(levels: Record<string, number>): string {
		const entries = Object.entries(levels);
		if (entries.length === 0) return '—';
		return entries
			.slice(0, 3)
			.map(([k, v]) => `${k} ${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`)
			.join(' · ');
	}

	interface Aggregate {
		long: number;
		short: number;
		noTrade: number;
	}

	function aggregate(items: ScannerResult[]): Aggregate {
		let long = 0;
		let short = 0;
		let noTrade = 0;
		for (const item of items) {
			if (!item.triggered) {
				noTrade += 1;
			} else if (item.direction === 'LONG') {
				long += 1;
			} else if (item.direction === 'SHORT') {
				short += 1;
			} else {
				noTrade += 1;
			}
		}
		return { long, short, noTrade };
	}
</script>

<svelte:head>
	<title>Portfolio · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="briefcase" class="text-accent" />
			Portfolio / Watchlist
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Scan a multi-symbol watchlist with a chosen scanner and review the signals at a glance.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[20rem_1fr]">
		<!-- Watchlist + config column -->
		<div class="space-y-6">
			<!-- Watchlist -->
			<section class="space-y-3 rounded-lg border border-base-700 bg-base-850 p-5">
				<h2 class="text-xs font-medium tracking-wide text-base-400 uppercase">Watchlist</h2>

				<div class="flex gap-2">
					<input
						type="text"
						bind:value={newSymbol}
						onkeydown={(e) => e.key === 'Enter' && addSymbol()}
						placeholder="Add symbol…"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
					<button
						type="button"
						onclick={addSymbol}
						class="flex shrink-0 items-center gap-1 rounded-md bg-base-800 px-3 py-2 text-sm text-base-200 hover:bg-base-700"
					>
						<Icon name="plus" />
					</button>
				</div>

				{#if watchlist.length === 0}
					<p class="text-xs text-base-500">No symbols yet.</p>
				{:else}
					<ul class="flex flex-wrap gap-2">
						{#each watchlist as sym (sym)}
							<li
								class="flex items-center gap-1.5 rounded-full border border-base-700 bg-base-900 py-1 pr-1.5 pl-3 text-xs font-medium text-base-100"
							>
								<span class="font-mono">{sym}</span>
								<button
									type="button"
									onclick={() => removeSymbol(sym)}
									class="flex h-4 w-4 items-center justify-center rounded-full text-base-500 hover:bg-base-700 hover:text-danger"
									aria-label={`Remove ${sym}`}
								>
									<Icon name="x" />
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</section>

			<!-- Scan config -->
			{#snippet configForm(scanners: Scanner[])}
				<section class="space-y-4 rounded-lg border border-base-700 bg-base-850 p-5">
					<h2 class="text-xs font-medium tracking-wide text-base-400 uppercase">Scan</h2>

					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">Scanner</span>
						<select
							bind:value={scannerId}
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
						>
							{#each scanners as scanner (scanner.scanner_id)}
								<option value={scanner.scanner_id}>{scanner.name}</option>
							{:else}
								<option value="" disabled>No scanners available</option>
							{/each}
						</select>
					</label>

					<div class="grid grid-cols-2 gap-3">
						<label class="block">
							<span class="mb-1 block text-xs font-medium text-base-300">Timeframe</span>
							<select
								bind:value={timeframe}
								class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
							>
								{#each TIMEFRAMES as tf (tf)}
									<option value={tf}>{tf}</option>
								{/each}
							</select>
						</label>
						<label class="block">
							<span class="mb-1 block text-xs font-medium text-base-300">History</span>
							<select
								bind:value={history}
								class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
							>
								{#each HISTORY_WINDOWS as hw (hw)}
									<option value={hw}>{hw}</option>
								{/each}
							</select>
						</label>
					</div>

					{#if errorMessage}
						<p class="flex items-center gap-1.5 text-sm text-danger">
							<Icon name="warning-circle" />
							{errorMessage}
						</p>
					{/if}

					<button
						type="button"
						onclick={() => submit(scanners)}
						disabled={submitting}
						class="flex w-full items-center justify-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
					>
						{#if submitting}
							<Icon name="spinner-gap" class="animate-spin" />
							Enqueuing…
						{:else}
							<Icon name="list-magnifying-glass" />
							Scan Watchlist
						{/if}
					</button>
				</section>
			{/snippet}

			<svelte:boundary>
				{#snippet pending()}
					<div class="h-64 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
				{/snippet}
				{@render configForm(await listScanners())}
				{#snippet failed(error, reset)}
					<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
						<Icon name="warning-circle" class="text-2xl text-danger" />
						<p class="mt-2 text-sm text-base-200">
							{error instanceof Error ? error.message : 'Failed to load scanners.'}
						</p>
						<button
							type="button"
							onclick={reset}
							class="mt-3 rounded-md bg-base-800 px-3 py-1.5 text-xs text-base-200"
						>
							retry
						</button>
					</div>
				{/snippet}
			</svelte:boundary>
		</div>

		<!-- Results panel -->
		<div class="min-w-0">
			{#if !activeRunId}
				<div
					class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-base-700 text-base-400"
				>
					<Icon name="briefcase" class="text-3xl" />
					<p>Scan your watchlist to see signals across all symbols.</p>
				</div>
			{:else}
				{#snippet runStatus(run: ScanRun)}
					{#if !isTerminal(run.status)}
						<div
							class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-base-700 bg-base-850 text-base-300"
						>
							<Icon name="spinner-gap" class="animate-spin text-3xl text-accent" />
							<p class="text-sm">
								Scan <span class="font-medium {statusTone(run.status)}">{run.status}</span>…
							</p>
							<p class="font-mono text-xs text-base-500">{run.run_id}</p>
						</div>
					{:else if run.status.toLowerCase() === 'error'}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">{run.error ?? 'Scan failed.'}</p>
						</div>
					{:else}
						<svelte:boundary>
							{#snippet pending()}
								<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
							{/snippet}
							{#await getScanResults(run.run_id) then { items }}
								{@const agg = aggregate(items)}
								<div class="space-y-6">
									<!-- Aggregate stats -->
									<div class="grid grid-cols-3 gap-3">
										<div class="rounded-lg border border-base-700 bg-base-850 p-3">
											<div class="text-[11px] tracking-wide text-base-500 uppercase">Long</div>
											<div class="mt-1 font-mono text-lg font-semibold text-long">{agg.long}</div>
										</div>
										<div class="rounded-lg border border-base-700 bg-base-850 p-3">
											<div class="text-[11px] tracking-wide text-base-500 uppercase">Short</div>
											<div class="mt-1 font-mono text-lg font-semibold text-short">{agg.short}</div>
										</div>
										<div class="rounded-lg border border-base-700 bg-base-850 p-3">
											<div class="text-[11px] tracking-wide text-base-500 uppercase">No Trade</div>
											<div class="mt-1 font-mono text-lg font-semibold text-base-300">
												{agg.noTrade}
											</div>
										</div>
									</div>

									<!-- Results table -->
									<div class="overflow-x-auto rounded-lg border border-base-700">
										<table class="w-full border-collapse text-sm">
											<thead>
												<tr
													class="bg-base-850 text-left text-xs tracking-wide text-base-400 uppercase"
												>
													<th class="px-3 py-2 font-medium">Symbol</th>
													<th class="px-3 py-2 font-medium">Classification</th>
													<th class="px-3 py-2 font-medium">Direction</th>
													<th class="px-3 py-2 text-right font-medium">Score</th>
													<th class="px-3 py-2 font-medium">Key Levels</th>
												</tr>
											</thead>
											<tbody>
												{#each items as result (result.id ?? result.symbol + result.run_id)}
													<tr class="border-t border-base-800 transition-colors hover:bg-base-850">
														<td class="px-3 py-2 font-mono font-semibold text-base-100">
															<span class="flex items-center gap-1.5">
																{#if result.triggered}
																	<Icon name="lightning" class="text-accent" label="triggered" />
																{/if}
																{result.symbol}
															</span>
														</td>
														<td class="px-3 py-2 text-base-200">{result.classification}</td>
														<td class="px-3 py-2">
															<span
																class="rounded-full border border-base-700 bg-base-900 px-2 py-0.5 text-xs font-medium {directionTone(
																	result.direction
																)}"
															>
																{result.direction ?? '—'}
															</span>
														</td>
														<td class="px-3 py-2 text-right font-mono text-accent">
															{(result.score * 100).toFixed(0)}
														</td>
														<td class="px-3 py-2 font-mono text-xs text-base-400">
															{fmtLevels(result.levels)}
														</td>
													</tr>
												{:else}
													<tr>
														<td colspan="5" class="px-3 py-8 text-center text-base-400">
															No results for this scan.
														</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								</div>
							{/await}
						</svelte:boundary>
					{/if}
				{/snippet}

				<svelte:boundary>
					{#snippet pending()}
						<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
					{/snippet}
					{@render runStatus(await getScan(activeRunId))}
					{#snippet failed(error, reset)}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">
								{error instanceof Error ? error.message : 'Failed to load scan.'}
							</p>
							<button
								type="button"
								onclick={reset}
								class="mt-3 rounded-md bg-base-800 px-3 py-1.5 text-xs text-base-200"
							>
								retry
							</button>
						</div>
					{/snippet}
				</svelte:boundary>
			{/if}
		</div>
	</div>
</div>
