<script lang="ts">
	import Icon from './Icon.svelte';
	import type { HealthResponse } from '$lib/types';

	interface Props {
		health: HealthResponse;
	}

	let { health }: Props = $props();

	const services = $derived([
		{ label: 'API', value: health.status },
		{ label: 'Postgres', value: health.db },
		{ label: 'Redis', value: health.redis },
		{ label: 'TimescaleDB', value: health.timescale }
	]);

	function isHealthy(value: string): boolean {
		const v = value?.toLowerCase?.() ?? '';
		return v === 'ok' || v === 'up' || v === 'healthy' || v === 'connected';
	}

	function ageTone(seconds: number): string {
		if (seconds <= 60) return 'text-ok';
		if (seconds <= 600) return 'text-warn';
		return 'text-danger';
	}

	function formatAge(seconds: number): string {
		if (seconds < 60) return `${Math.round(seconds)}s`;
		if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
		return `${(seconds / 3600).toFixed(1)}h`;
	}
</script>

<section class="rounded-lg border border-base-700 bg-base-850 p-4">
	<header class="mb-3 flex items-center gap-2">
		<Icon name="heartbeat" class="text-lg text-accent" />
		<h2 class="text-sm font-semibold tracking-wide text-base-100 uppercase">Data Health</h2>
	</header>

	<div class="mb-4 grid grid-cols-2 gap-2">
		{#each services as service (service.label)}
			<div class="flex items-center justify-between rounded-md bg-base-900 px-3 py-2">
				<span class="text-xs text-base-300">{service.label}</span>
				<span class="flex items-center gap-1.5 text-xs font-medium">
					<Icon
						name={isHealthy(service.value) ? 'check-circle' : 'x-circle'}
						class={isHealthy(service.value) ? 'text-ok' : 'text-danger'}
					/>
					<span class={isHealthy(service.value) ? 'text-ok' : 'text-danger'}>
						{service.value}
					</span>
				</span>
			</div>
		{/each}
	</div>

	<h3 class="mb-2 text-xs font-medium tracking-wide text-base-400 uppercase">Feed Freshness</h3>
	{#if health.data_health.length === 0}
		<p class="text-xs text-base-400">No tracked feeds.</p>
	{:else}
		<ul class="space-y-1">
			{#each health.data_health as feed (feed.symbol + feed.timeframe)}
				<li class="flex items-center justify-between text-xs">
					<span class="font-mono text-base-200">
						{feed.symbol}
						<span class="text-base-500">·</span>
						{feed.timeframe}
					</span>
					<span class="flex items-center gap-1 {ageTone(feed.last_bar_age_seconds)}">
						<Icon name="clock" />
						{formatAge(feed.last_bar_age_seconds)} old
					</span>
				</li>
			{/each}
		</ul>
	{/if}
</section>
