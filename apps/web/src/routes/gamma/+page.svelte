<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import EvidencePanel from '$lib/components/EvidencePanel.svelte';
	import GammaProfileChart from '$lib/components/GammaProfileChart.svelte';
	import { getGammaResult, getGammaRun, runGammaScan } from './data.remote';
	import type { ScannerResult } from '$lib/types';

	const TIMEFRAMES = ['1m', '5m', '15m', '1h'] as const;

	let underlying = $state('SPY');
	let timeframe = $state('5m');

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	// Active run id drives the result panel + polling.
	let runId = $state<string | null>(null);

	function isFinished(status: string | undefined): boolean {
		const s = status?.toLowerCase();
		return s === 'finished' || s === 'error';
	}

	// Poll the run until it finishes.
	$effect(() => {
		const id = runId;
		if (!id) return;
		const status = getGammaRun(id).current?.status;
		if (isFinished(status)) return;
		const handle = setInterval(() => {
			getGammaRun(id).refresh();
		}, 1500);
		return () => clearInterval(handle);
	});

	async function submit(): Promise<void> {
		errorMessage = null;
		if (!underlying.trim()) {
			errorMessage = 'Enter an underlying.';
			return;
		}
		submitting = true;
		try {
			const { run_id } = await runGammaScan({
				underlying: underlying.trim().toUpperCase(),
				timeframe
			});
			runId = run_id;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start gamma scan.';
		} finally {
			submitting = false;
		}
	}

	const LEVEL_CHIPS: { key: string; label: string }[] = [
		{ key: 'spot', label: 'Spot' },
		{ key: 'flip', label: 'Gamma Flip' },
		{ key: 'call_wall', label: 'Call Wall' },
		{ key: 'put_wall', label: 'Put Wall' }
	];

	function fmtLevel(value: number | undefined): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
	}

	function directionTone(direction: string | undefined): string {
		if (direction === 'LONG') return 'text-long';
		if (direction === 'SHORT') return 'text-short';
		return 'text-base-300';
	}
</script>

<svelte:head>
	<title>SPX Gamma Lab · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-6xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="chart-bar" class="text-accent" />
			SPX Gamma Lab
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Run the SPX gamma command scanner and inspect dealer positioning levels.
		</p>
	</header>

	<!-- Config bar -->
	<section
		class="mb-6 flex flex-wrap items-end gap-4 rounded-lg border border-base-700 bg-base-850 p-4"
	>
		<label class="block">
			<span class="mb-1 block text-xs font-medium text-base-300">Underlying</span>
			<input
				type="text"
				bind:value={underlying}
				placeholder="SPY"
				class="w-32 rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
			/>
		</label>
		<label class="block">
			<span class="mb-1 block text-xs font-medium text-base-300">Timeframe</span>
			<select
				bind:value={timeframe}
				class="w-28 rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
			>
				{#each TIMEFRAMES as tf (tf)}
					<option value={tf}>{tf}</option>
				{/each}
			</select>
		</label>
		<button
			type="button"
			onclick={submit}
			disabled={submitting}
			class="flex items-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
		>
			{#if submitting}
				<Icon name="spinner-gap" class="animate-spin" />
				Running…
			{:else}
				<Icon name="play" />
				Run Gamma Scan
			{/if}
		</button>
		{#if errorMessage}
			<p class="flex items-center gap-1.5 text-sm text-danger">
				<Icon name="warning-circle" />
				{errorMessage}
			</p>
		{/if}
	</section>

	{#if !runId}
		<div
			class="flex h-80 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-base-700 text-base-400"
		>
			<Icon name="chart-bar" class="text-3xl" />
			<p>Run a gamma scan to view the latest dealer positioning snapshot.</p>
		</div>
	{:else}
		{#snippet pendingPanel()}
			<div
				class="flex h-80 flex-col items-center justify-center gap-3 rounded-lg border border-base-700 bg-base-850 text-base-300"
			>
				<Icon name="spinner-gap" class="animate-spin text-3xl text-accent" />
				<p class="text-sm">Scanning…</p>
			</div>
		{/snippet}

		{#snippet runError(message: string)}
			<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
				<Icon name="warning-circle" class="text-2xl text-danger" />
				<p class="mt-2 text-sm text-base-200">{message}</p>
			</div>
		{/snippet}

		{#snippet resultView(result: ScannerResult)}
			<div class="space-y-6">
				<!-- Headline -->
				<section
					class="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-base-700 bg-base-850 p-4"
				>
					<div class="flex items-center gap-3">
						<span
							class="rounded-full border border-accent/40 bg-base-900 px-3 py-1 text-sm font-semibold text-accent"
						>
							{result.classification}
						</span>
						<span
							class="flex items-center gap-1.5 text-sm font-medium {directionTone(
								result.direction
							)}"
						>
							<Icon name="arrows-out-cardinal" />
							{result.direction ?? 'NEUTRAL'}
						</span>
						<span class="font-mono text-sm text-base-400">{result.symbol}</span>
					</div>
					<div class="flex items-center gap-2 text-sm">
						<span class="text-base-400">Score</span>
						<span class="font-mono text-lg font-semibold text-base-50">
							{result.score.toFixed(2)}
						</span>
					</div>
				</section>

				<!-- Key level chips -->
				<section class="flex flex-wrap gap-3">
					{#each LEVEL_CHIPS as chip (chip.key)}
						<div class="rounded-lg border border-base-700 bg-base-850 px-4 py-2">
							<div class="text-[11px] tracking-wide text-base-500 uppercase">{chip.label}</div>
							<div class="mt-0.5 font-mono text-base font-semibold text-base-50">
								{fmtLevel(result.levels?.[chip.key])}
							</div>
						</div>
					{/each}
				</section>

				<!-- Gamma profile chart -->
				<GammaProfileChart levels={result.levels} meta={result.meta} />

				<!-- Evidence -->
				<EvidencePanel evidence={result.evidence} />
			</div>
		{/snippet}

		<svelte:boundary>
			{#snippet pending()}
				{@render pendingPanel()}
			{/snippet}

			{@const run = await getGammaRun(runId)}
			{#if !isFinished(run.status)}
				{@render pendingPanel()}
			{:else if run.status.toLowerCase() === 'error'}
				{@render runError(run.error ?? 'Gamma scan failed.')}
			{:else}
				{@const result = await getGammaResult(runId)}
				{#if result}
					{@render resultView(result)}
				{:else}
					{@render runError('Scan finished but produced no gamma result.')}
				{/if}
			{/if}

			{#snippet failed(error, reset)}
				<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
					<Icon name="warning-circle" class="text-2xl text-danger" />
					<p class="mt-2 text-sm text-base-200">
						{error instanceof Error ? error.message : 'Failed to load gamma scan.'}
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
