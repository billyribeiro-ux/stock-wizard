<script lang="ts">
	import { goto } from '$app/navigation';
	import { SvelteSet } from 'svelte/reactivity';
	import Icon from '$lib/components/Icon.svelte';
	import { listScanners, listEdgeWeights, runEnsembleScan } from './data.remote';
	import type { Scanner } from '$lib/types';
	import type { EdgeWeight } from '$lib/server/api';

	const TIMEFRAMES = ['1d', '1w'] as const;
	const HISTORY_WINDOWS = ['1y', '2y', '5y'] as const;

	const selected = new SvelteSet<string>();
	let symbolsInput = $state('SPY, QQQ, AAPL');
	let timeframe = $state('1d');
	let history = $state('2y');
	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	const symbols = $derived(
		symbolsInput
			.split(/[,\s]+/)
			.map((s) => s.trim().toUpperCase())
			.filter(Boolean)
	);

	function toggle(id: string): void {
		if (selected.has(id)) selected.delete(id);
		else selected.add(id);
	}

	/** Map scanner_id -> edge record for the proven/regime badges. */
	function edgeMap(items: EdgeWeight[]): Record<string, EdgeWeight> {
		const out: Record<string, EdgeWeight> = {};
		for (const e of items) out[e.scanner_id] = e;
		return out;
	}

	function edgeTone(w: number | null | undefined): string {
		if (w === null || w === undefined) return 'text-base-500';
		if (w >= 1.05) return 'text-long';
		if (w <= 0.95) return 'text-short';
		return 'text-base-300';
	}

	async function submit(): Promise<void> {
		errorMessage = null;
		if (selected.size < 2) {
			errorMessage = 'Pick at least two scanners to fuse.';
			return;
		}
		if (symbols.length === 0) {
			errorMessage = 'Enter at least one symbol.';
			return;
		}
		submitting = true;
		try {
			const { run_id } = await runEnsembleScan({
				scanners: [...selected],
				symbols,
				timeframe,
				history
			});
			await goto(`/results?run=${encodeURIComponent(run_id)}`);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start ensemble scan.';
		} finally {
			submitting = false;
		}
	}
</script>

<svelte:head>
	<title>Ensemble · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-5xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="graph" class="text-accent" />
			Regime-Conditional Ensemble
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Fuse multiple scanners into one consensus. Each scanner votes weighted by its
			<em>current-regime</em> out-of-sample edge; scanners with no proven edge in the live regime are
			dropped automatically. This is the strategy that more than doubled the best single scanner out-of-sample.
		</p>
	</header>

	{#snippet builder(scanners: Scanner[], edges: Record<string, EdgeWeight>)}
		<div class="grid gap-6 lg:grid-cols-[1fr_18rem]">
			<!-- Scanner multi-select -->
			<section class="rounded-lg border border-base-700 bg-base-850 p-5">
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-sm font-semibold text-base-100">Scanners to fuse</h2>
					<span class="text-[11px] text-base-500">{selected.size} selected</span>
				</div>
				<div class="grid max-h-[28rem] gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2">
					{#each scanners as scanner (scanner.scanner_id)}
						{@const e = edges[scanner.scanner_id]}
						<button
							type="button"
							onclick={() => toggle(scanner.scanner_id)}
							class="flex items-start gap-2 rounded-md border p-2 text-left transition-colors"
							class:border-accent={selected.has(scanner.scanner_id)}
							class:bg-base-900={selected.has(scanner.scanner_id)}
							class:border-base-700={!selected.has(scanner.scanner_id)}
						>
							<Icon
								name={selected.has(scanner.scanner_id) ? 'check-square' : 'square'}
								class={selected.has(scanner.scanner_id) ? 'text-accent' : 'text-base-500'}
							/>
							<span class="min-w-0">
								<span class="block truncate text-xs font-medium text-base-100">{scanner.name}</span>
								{#if e}
									<span class="flex flex-wrap gap-x-2 text-[10px]">
										<span class={edgeTone(e.edge_weight)}>×{(e.edge_weight ?? 1).toFixed(2)}</span>
										{#each Object.entries(e.regime_edges ?? {}) as [regime, w] (regime)}
											<span class="text-base-500"
												>{regime}<span class={edgeTone(w)}>×{w.toFixed(2)}</span></span
											>
										{/each}
									</span>
								{:else}
									<span class="text-[10px] text-base-600">unvalidated</span>
								{/if}
							</span>
						</button>
					{/each}
				</div>
			</section>

			<!-- Config -->
			<section class="space-y-4 rounded-lg border border-base-700 bg-base-850 p-5">
				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">Symbols</span>
					<input
						type="text"
						bind:value={symbolsInput}
						placeholder="SPY, QQQ, AAPL"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
					<span class="mt-1 block text-[11px] text-base-500">
						{symbols.length} symbol{symbols.length === 1 ? '' : 's'}
					</span>
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
					onclick={submit}
					disabled={submitting || selected.size < 2}
					class="flex w-full items-center justify-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
				>
					{#if submitting}
						<Icon name="spinner-gap" class="animate-spin" />
						Dispatching…
					{:else}
						<Icon name="graph" />
						Run Ensemble
					{/if}
				</button>
				<p class="text-[11px] text-base-500">
					Per-regime weights come from the walk-forward roster validation (run it in the ML Lab).
					Unvalidated scanners vote at neutral weight.
				</p>
			</section>
		</div>
	{/snippet}

	<svelte:boundary>
		{#snippet pending()}
			<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
		{/snippet}

		{@render builder(await listScanners(), edgeMap((await listEdgeWeights()).items))}

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
