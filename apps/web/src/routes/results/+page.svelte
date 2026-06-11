<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import Icon from '$lib/components/Icon.svelte';
	import ResultsTable from '$lib/components/ResultsTable.svelte';
	import SignalCard from '$lib/components/SignalCard.svelte';
	import { getResults, getRun, liveSignals } from './data.remote';
	import { SignalStream } from '$lib/state/stream.svelte';
	import type { ScanRun, ScannerResult, ScannerResultsResponse } from '$lib/types';

	const runId = $derived(page.url.searchParams.get('run') ?? '');

	// Live signal buffer for the side panel.
	const stream = new SignalStream(50);

	// Own the live query so SvelteKit keeps the stream connected while mounted.
	const live = $derived(runId ? liveSignals(runId) : null);

	// Feed streamed values into the reactive buffer + track connection state.
	$effect(() => {
		if (!live) {
			stream.setConnected(false);
			return;
		}
		stream.setConnected(live.connected);
		const latest = live.current;
		if (latest) stream.push(latest);
	});

	function openResult(result: ScannerResult): void {
		const id = result.id ?? `${result.run_id}:${result.symbol}:${result.scanner_id}`;
		goto(`/results/${encodeURIComponent(id)}`);
	}

	function statusTone(status: string): string {
		const s = status?.toLowerCase();
		if (s === 'finished') return 'text-ok';
		if (s === 'error') return 'text-danger';
		if (s === 'running' || s === 'queued') return 'text-warn';
		return 'text-base-300';
	}
</script>

<svelte:head>
	<title>Results · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6 flex items-center justify-between">
		<div>
			<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
				<Icon name="table" class="text-accent" />
				Results
			</h1>
			{#if runId}
				<p class="mt-1 font-mono text-xs text-base-400">run {runId}</p>
			{/if}
		</div>
		<a href="/scanners" class="flex items-center gap-2 text-sm text-accent hover:underline">
			<Icon name="plus" />
			New Scan
		</a>
	</header>

	{#if !runId}
		<div
			class="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-base-700 text-base-400"
		>
			<Icon name="magnifying-glass" class="text-3xl" />
			<p>No run selected. Start a scan from the builder.</p>
			<a
				href="/scanners"
				class="rounded-md bg-accent-strong px-3 py-2 text-sm font-semibold text-base-950"
			>
				Go to Scanner Builder
			</a>
		</div>
	{:else}
		<div class="grid gap-6 lg:grid-cols-[1fr_22rem]">
			<!-- Run status snippet -->
			{#snippet runStatus(run: ScanRun)}
				<div
					class="flex items-center justify-between rounded-md border border-base-700 bg-base-850 px-4 py-2 text-sm"
				>
					<span class="flex items-center gap-2">
						<Icon name="crosshair" class="text-base-400" />
						<span class="text-base-300">{run.scanner_id}</span>
					</span>
					<span class="flex items-center gap-1.5 font-medium {statusTone(run.status)}">
						<Icon name="circle" />
						{run.status}
					</span>
				</div>
			{/snippet}

			{#snippet resultsTable(data: ScannerResultsResponse)}
				<div class="space-y-2">
					<div class="flex items-center justify-between text-xs text-base-400">
						<span>{data.total} result{data.total === 1 ? '' : 's'}</span>
						<button
							type="button"
							onclick={() => getResults(runId).refresh()}
							class="flex items-center gap-1 hover:text-base-200"
						>
							<Icon name="clock-clockwise" />
							refresh
						</button>
					</div>
					<ResultsTable results={data.items} onselect={openResult} />
				</div>
			{/snippet}

			<!-- Boundary snippets (named uniquely to avoid scope collisions) -->
			{#snippet statusPending()}
				<div class="h-10 animate-pulse rounded-md bg-base-850"></div>
			{/snippet}

			{#snippet statusFailed()}
				<div class="rounded-md border border-danger/40 bg-base-850 px-4 py-2 text-sm text-danger">
					Run status unavailable.
				</div>
			{/snippet}

			{#snippet tablePending()}
				<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
			{/snippet}

			{#snippet tableFailed(error: unknown, reset: () => void)}
				<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center text-sm">
					<Icon name="warning-circle" class="text-2xl text-danger" />
					<p class="mt-2 text-base-200">
						{error instanceof Error ? error.message : 'Failed to load results.'}
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

			<!-- Results table -->
			<div class="space-y-4">
				<!-- Run status -->
				<svelte:boundary pending={statusPending} failed={statusFailed}>
					{@render runStatus(await getRun(runId))}
				</svelte:boundary>

				<!-- Table -->
				<svelte:boundary pending={tablePending} failed={tableFailed}>
					{@render resultsTable(await getResults(runId))}
				</svelte:boundary>
			</div>

			<!-- Live signals side panel -->
			<aside class="rounded-lg border border-base-700 bg-base-850 p-4">
				<header class="mb-3 flex items-center justify-between">
					<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
						<Icon name="broadcast" class="text-accent" />
						Signals
					</h2>
					<span
						class="flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-bold"
						class:bg-long-soft={stream.connected}
						class:text-long={stream.connected}
						class:bg-base-800={!stream.connected}
						class:text-base-400={!stream.connected}
					>
						<span
							class="h-1.5 w-1.5 rounded-full"
							class:bg-long={stream.connected}
							class:animate-pulse={stream.connected}
							class:bg-base-500={!stream.connected}
						></span>
						{stream.connected ? 'LIVE' : 'OFFLINE'}
					</span>
				</header>

				{#if stream.count === 0}
					<div
						class="flex h-40 flex-col items-center justify-center gap-2 text-center text-xs text-base-500"
					>
						<Icon name="pulse" class="text-2xl" />
						Listening for live signals on this run…
					</div>
				{:else}
					<div class="max-h-[32rem] space-y-2 overflow-y-auto pr-1">
						{#each stream.signals as signal (signal.signal_id)}
							<SignalCard {signal} compact />
						{/each}
					</div>
				{/if}
			</aside>
		</div>
	{/if}
</div>
