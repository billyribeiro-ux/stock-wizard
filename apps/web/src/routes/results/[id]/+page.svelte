<script lang="ts">
	import { page } from '$app/state';
	import Icon from '$lib/components/Icon.svelte';
	import EvidencePanel from '$lib/components/EvidencePanel.svelte';
	import GammaProfileChart from '$lib/components/GammaProfileChart.svelte';
	import { getResult } from '../data.remote';
	import type { ScannerResult } from '$lib/types';

	const id = $derived(page.params.id ?? '');

	function directionTone(direction: string | undefined): string {
		if (direction === 'LONG') return 'text-long bg-long-soft';
		if (direction === 'SHORT') return 'text-short bg-short-soft';
		return 'text-neutral-signal bg-base-800';
	}

	function isGamma(classification: string): boolean {
		return /gamma|gex|dealer/i.test(classification ?? '');
	}

	function num(value: number): string {
		return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
	}
</script>

<svelte:head>
	<title>Evidence · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-5xl">
	<a
		href="/results?run="
		onclick={(e) => {
			e.preventDefault();
			history.back();
		}}
		class="mb-4 inline-flex items-center gap-1.5 text-sm text-base-400 hover:text-base-200"
	>
		<Icon name="arrow-up" class="rotate-[-90deg]" />
		Back to results
	</a>

	{#snippet detail(result: ScannerResult)}
		<!-- Header -->
		<header class="mb-6 rounded-lg border border-base-700 bg-base-850 p-5">
			<div class="flex flex-wrap items-center gap-3">
				<span class="font-mono text-2xl font-bold text-base-50">{result.symbol}</span>
				<span class="text-sm text-base-400">{result.timeframe}</span>
				<span class="rounded px-2 py-0.5 text-xs font-bold {directionTone(result.direction)}">
					{result.direction ?? 'NEUTRAL'}
				</span>
				{#if result.triggered}
					<span class="flex items-center gap-1 rounded bg-base-800 px-2 py-0.5 text-xs text-accent">
						<Icon name="lightning" /> triggered
					</span>
				{/if}
				<span class="ml-auto flex items-center gap-2 text-sm">
					<span class="text-base-400">score</span>
					<span class="font-mono text-lg font-bold text-accent">
						{(result.score * 100).toFixed(0)}
					</span>
				</span>
			</div>
			<div class="mt-2 flex flex-wrap items-center gap-4 text-xs text-base-400">
				<span class="flex items-center gap-1">
					<Icon name="crosshair" />
					{result.scanner_id}
				</span>
				<span class="flex items-center gap-1">
					<Icon name="flag" />
					{result.classification}
				</span>
				<span class="flex items-center gap-1">
					<Icon name="clock" />
					{result.ts}
				</span>
			</div>

			{#if Object.keys(result.levels ?? {}).length > 0}
				<div class="mt-4 flex flex-wrap gap-2">
					{#each Object.entries(result.levels) as [name, value] (name)}
						<span class="rounded-md bg-base-900 px-2.5 py-1 text-xs">
							<span class="text-base-500">{name}</span>
							<span class="ml-1.5 font-mono text-base-200">{num(value)}</span>
						</span>
					{/each}
				</div>
			{/if}
		</header>

		<!-- Gamma chart when relevant -->
		{#if isGamma(result.classification)}
			<div class="mb-6">
				<GammaProfileChart
					levels={result.levels}
					meta={result.meta ?? {}}
					title="{result.symbol} · Gamma Exposure by Strike"
				/>
			</div>
		{/if}

		<!-- Evidence -->
		<EvidencePanel evidence={result.evidence} />
	{/snippet}

	<svelte:boundary>
		{#snippet pending()}
			<div class="space-y-4">
				<div class="h-24 animate-pulse rounded-lg bg-base-850"></div>
				<div class="h-96 animate-pulse rounded-lg bg-base-850"></div>
			</div>
		{/snippet}

		{@render detail(await getResult(id))}

		{#snippet failed(error, reset)}
			<div class="rounded-lg border border-danger/40 bg-base-850 p-8 text-center">
				<Icon name="warning-circle" class="text-3xl text-danger" />
				<p class="mt-2 text-sm text-base-200">
					{error instanceof Error ? error.message : 'Failed to load this result.'}
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
