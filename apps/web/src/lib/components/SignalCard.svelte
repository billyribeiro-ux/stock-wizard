<script lang="ts">
	import Icon from './Icon.svelte';
	import type { SignalPacket } from '$lib/types';

	interface Props {
		signal: SignalPacket;
		compact?: boolean;
	}

	let { signal, compact = false }: Props = $props();

	const sideMeta = $derived.by(() => {
		switch (signal.side) {
			case 'LONG':
				return { tone: 'text-long', bg: 'bg-long-soft', icon: 'trend-up', label: 'LONG' };
			case 'SHORT':
				return { tone: 'text-short', bg: 'bg-short-soft', icon: 'trend-down', label: 'SHORT' };
			default:
				return { tone: 'text-neutral-signal', bg: 'bg-base-800', icon: 'minus', label: 'NEUTRAL' };
		}
	});

	function num(value: number | undefined): string {
		if (value === undefined || Number.isNaN(value)) return '—';
		return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
	}

	// Edge weight: show a chip only when it meaningfully departs from neutral (1.0).
	const edge = $derived.by(() => {
		const w = signal.edge_weight;
		if (w === undefined || Math.abs(w - 1) < 0.05) return null;
		return {
			label: `×${w.toFixed(2)}`,
			tone: w >= 1 ? 'text-long bg-long-soft' : 'text-short bg-short-soft',
			title: w >= 1 ? 'Validated edge — proven scanner' : 'Under-performing scanner (damped)'
		};
	});

	const gated = $derived(signal.regime_aligned === false);

	function time(iso: string): string {
		const date = new Date(iso);
		return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString();
	}
</script>

<article
	class="rounded-md border border-base-700 bg-base-850 p-3 transition-colors hover:border-base-600"
>
	<header class="flex items-center justify-between gap-2">
		<div class="flex items-center gap-2">
			<span
				class="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-bold {sideMeta.tone} {sideMeta.bg}"
			>
				<Icon name={sideMeta.icon} />
				{sideMeta.label}
			</span>
			<span class="font-mono text-sm font-semibold text-base-100">{signal.symbol}</span>
			<span class="text-xs text-base-400">{signal.timeframe}</span>
			{#if gated}
				<span
					class="flex items-center gap-1 rounded border border-warn/40 bg-base-800 px-1.5 py-0.5 text-[10px] font-medium text-warn"
					title="Regime-gated: this scanner has no validated edge in the current regime — trade plan suppressed"
				>
					<Icon name="warning" />
					gated
				</span>
			{/if}
		</div>
		<span class="text-xs text-base-500">{time(signal.created_at)}</span>
	</header>

	<p class="mt-1 truncate text-xs text-base-300" title={signal.evidence?.why}>
		{signal.evidence?.why ?? signal.source_scanner}
	</p>

	{#if !compact}
		<div class="mt-2 grid grid-cols-3 gap-2 text-xs">
			<div class="rounded bg-base-900 px-2 py-1">
				<div class="text-[10px] text-base-500 uppercase">Entry</div>
				<div class="font-mono text-base-100">{num(signal.entry)}</div>
			</div>
			<div class="rounded bg-base-900 px-2 py-1">
				<div class="text-[10px] text-base-500 uppercase">Stop</div>
				<div class="font-mono text-short">{num(signal.stop)}</div>
			</div>
			<div class="rounded bg-base-900 px-2 py-1">
				<div class="text-[10px] text-base-500 uppercase">Target</div>
				<div class="font-mono text-long">{num(signal.targets?.[0])}</div>
			</div>
		</div>
	{/if}

	<footer class="mt-2 flex items-center justify-between text-[11px] text-base-400">
		<span class="flex items-center gap-1">
			<Icon name="scan" />
			{signal.source_scanner}
		</span>
		<span class="flex items-center gap-2">
			{#if edge}
				<span class="rounded px-1.5 py-0.5 font-mono {edge.tone}" title={edge.title}>
					{edge.label}
				</span>
			{/if}
			<span class="rounded bg-base-800 px-1.5 py-0.5 text-base-300">{signal.regime}</span>
			<span class="font-mono text-accent">{(signal.score * 100).toFixed(0)}</span>
		</span>
	</footer>
</article>
