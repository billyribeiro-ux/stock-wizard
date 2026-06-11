<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import DataHealthCard from '$lib/components/DataHealthCard.svelte';
	import SignalCard from '$lib/components/SignalCard.svelte';
	import { getHealth, getRecentSignals } from './health.remote';
	import type { SignalPacket } from '$lib/types';

	const skeletonRows = [0, 1, 2];
</script>

<svelte:head>
	<title>Command Center · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-6xl space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
				<Icon name="gauge" class="text-accent" />
				Command Center
			</h1>
			<p class="mt-1 text-sm text-base-400">
				Live posture across feeds, scanners and the most recent signals.
			</p>
		</div>
		<a
			href="/scanners"
			class="flex items-center gap-2 rounded-md bg-accent-strong px-3 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent"
		>
			<Icon name="play" />
			New Scan
		</a>
	</div>

	<div class="grid gap-6 lg:grid-cols-3">
		<!-- Data health -->
		<div class="lg:col-span-1">
			<svelte:boundary>
				{#snippet pending()}
					<div class="h-64 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
				{/snippet}

				<DataHealthCard health={await getHealth()} />

				{#snippet failed(_error, reset)}
					<div class="rounded-lg border border-danger/40 bg-base-850 p-4 text-sm text-danger">
						<p class="flex items-center gap-2 font-medium">
							<Icon name="warning-circle" /> Health unavailable
						</p>
						<button type="button" onclick={reset} class="mt-2 text-xs text-base-300 underline">
							retry
						</button>
					</div>
				{/snippet}
			</svelte:boundary>
		</div>

		<!-- Recent signals -->
		<section class="rounded-lg border border-base-700 bg-base-850 p-4 lg:col-span-2">
			<header class="mb-3 flex items-center justify-between">
				<h2
					class="flex items-center gap-2 text-sm font-semibold tracking-wide text-base-100 uppercase"
				>
					<Icon name="pulse" class="text-accent" />
					Recent Signals
				</h2>
				<a href="/results" class="text-xs text-accent hover:underline">view all</a>
			</header>

			{#snippet grid(signals: SignalPacket[])}
				{#if signals.length === 0}
					<div class="flex h-40 flex-col items-center justify-center gap-2 text-sm text-base-500">
						<Icon name="broadcast" class="text-2xl" />
						No signals yet. Run a scanner to populate the feed.
					</div>
				{:else}
					<div class="grid gap-2 sm:grid-cols-2">
						{#each signals.slice(0, 6) as signal (signal.signal_id)}
							<SignalCard {signal} />
						{/each}
					</div>
				{/if}
			{/snippet}

			<svelte:boundary>
				{#snippet pending()}
					<div class="space-y-2">
						{#each skeletonRows as row (row)}
							<div class="h-24 animate-pulse rounded-md bg-base-900"></div>
						{/each}
					</div>
				{/snippet}

				{@render grid((await getRecentSignals()).items)}

				{#snippet failed(_error, reset)}
					<div class="flex h-40 flex-col items-center justify-center gap-2 text-sm text-danger">
						<Icon name="warning-circle" class="text-2xl" />
						Could not load signals.
						<button type="button" onclick={reset} class="text-xs text-base-300 underline">
							retry
						</button>
					</div>
				{/snippet}
			</svelte:boundary>
		</section>
	</div>

	<!-- Live mini-feed -->
	<section class="rounded-lg border border-base-700 bg-base-850 p-4">
		<header class="mb-3 flex items-center gap-2">
			<Icon name="broadcast" class="text-accent" />
			<h2 class="text-sm font-semibold tracking-wide text-base-100 uppercase">Live Mini-Feed</h2>
			<span class="ml-auto text-xs text-base-500">latest across all runs</span>
		</header>

		{#snippet ticker(signals: SignalPacket[])}
			{#if signals.length === 0}
				<p class="py-4 text-center text-xs text-base-500">Waiting for live signals…</p>
			{:else}
				<ul class="divide-y divide-base-800">
					{#each signals.slice(0, 8) as signal (signal.signal_id)}
						<li class="flex items-center gap-3 py-2 text-sm">
							<span
								class="font-mono text-xs"
								class:text-long={signal.side === 'LONG'}
								class:text-short={signal.side === 'SHORT'}
								class:text-neutral-signal={signal.side === 'NEUTRAL'}
							>
								{signal.side}
							</span>
							<span class="font-mono font-semibold text-base-100">{signal.symbol}</span>
							<span class="truncate text-xs text-base-400">{signal.evidence?.why}</span>
							<span class="ml-auto font-mono text-xs text-accent">
								{(signal.score * 100).toFixed(0)}
							</span>
						</li>
					{/each}
				</ul>
			{/if}
		{/snippet}

		<svelte:boundary>
			{#snippet pending()}
				<div class="h-16 animate-pulse rounded-md bg-base-900"></div>
			{/snippet}

			{@render ticker((await getRecentSignals()).items)}

			{#snippet failed(_error, reset)}
				<button type="button" onclick={reset} class="text-xs text-base-300 underline">
					feed offline · retry
				</button>
			{/snippet}
		</svelte:boundary>
	</section>
</div>
