<script lang="ts">
	import Icon from './Icon.svelte';
	import type { EvidenceItem, EvidencePacket } from '$lib/types';

	interface Props {
		evidence: EvidencePacket;
	}

	let { evidence }: Props = $props();

	function formatValue(value: unknown): string {
		if (value === null || value === undefined) return '—';
		if (typeof value === 'number') {
			return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
		}
		if (typeof value === 'object') return JSON.stringify(value);
		return String(value);
	}

	function formatReturn(value: number | undefined): string {
		if (value === undefined || Number.isNaN(value)) return '—';
		const pct = (value * 100).toFixed(1);
		return `${value >= 0 ? '+' : ''}${pct}%`;
	}

	const confidencePct = $derived(Math.round((evidence.confidence ?? 0) * 100));
</script>

{#snippet evidenceList(items: EvidenceItem[], tone: 'for' | 'against')}
	{#if items.length === 0}
		<p class="text-xs text-base-500">None recorded.</p>
	{:else}
		<ul class="space-y-1.5">
			{#each items as item, i (item.label + i)}
				<li class="rounded-md bg-base-900 px-3 py-2">
					<div class="flex items-center justify-between gap-2">
						<span class="text-xs font-medium text-base-100">{item.label}</span>
						<span class="font-mono text-xs {tone === 'for' ? 'text-long' : 'text-short'}">
							{formatValue(item.value)}
						</span>
					</div>
					<div class="mt-0.5 flex items-center justify-between text-[11px] text-base-500">
						<span>{item.kind} · {item.source}</span>
						<span>w {item.weight.toFixed(2)}</span>
					</div>
				</li>
			{/each}
		</ul>
	{/if}
{/snippet}

<div class="space-y-5">
	<!-- Narrative -->
	<section class="rounded-lg border border-base-700 bg-base-850 p-4">
		<div class="mb-3 flex items-center justify-between">
			<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
				<Icon name="brain" class="text-accent" />
				Thesis
			</h2>
			<div class="flex items-center gap-2 text-xs">
				<span class="text-base-400">Confidence</span>
				<div class="h-1.5 w-24 overflow-hidden rounded-full bg-base-800">
					<div class="h-full rounded-full bg-accent" style="width: {confidencePct}%"></div>
				</div>
				<span class="font-mono text-accent">{confidencePct}%</span>
			</div>
		</div>
		<dl class="space-y-3 text-sm">
			<div>
				<dt class="text-xs tracking-wide text-base-500 uppercase">Why</dt>
				<dd class="mt-0.5 text-base-200">{evidence.why}</dd>
			</div>
			<div>
				<dt class="text-xs tracking-wide text-base-500 uppercase">Why now</dt>
				<dd class="mt-0.5 text-base-200">{evidence.why_now}</dd>
			</div>
		</dl>
	</section>

	<!-- For / Against -->
	<div class="grid gap-4 md:grid-cols-2">
		<section class="rounded-lg border border-long/30 bg-base-850 p-4">
			<h3 class="mb-2 flex items-center gap-2 text-sm font-semibold text-long">
				<Icon name="thumbs-up" />
				Evidence For
			</h3>
			{@render evidenceList(evidence.evidence_for ?? [], 'for')}
		</section>
		<section class="rounded-lg border border-short/30 bg-base-850 p-4">
			<h3 class="mb-2 flex items-center gap-2 text-sm font-semibold text-short">
				<Icon name="thumbs-down" />
				Evidence Against
			</h3>
			{@render evidenceList(evidence.evidence_against ?? [], 'against')}
		</section>
	</div>

	<!-- Invalidation -->
	<section class="rounded-lg border border-warn/40 bg-base-850 p-4">
		<h3 class="mb-1 flex items-center gap-2 text-sm font-semibold text-warn">
			<Icon name="warning" />
			Invalidation
		</h3>
		<p class="text-sm text-base-200">{evidence.invalidation}</p>
	</section>

	<!-- Historical analogs -->
	<section class="rounded-lg border border-base-700 bg-base-850 p-4">
		<h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="clock-clockwise" class="text-accent" />
			Historical Analogs
		</h3>
		{#if (evidence.historical_analogs ?? []).length === 0}
			<p class="text-xs text-base-500">No analogs found.</p>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-xs">
					<thead>
						<tr class="text-left text-base-500">
							<th class="py-1 pr-3 font-medium">Date</th>
							<th class="py-1 pr-3 font-medium">Symbol</th>
							<th class="py-1 pr-3 text-right font-medium">Similarity</th>
							<th class="py-1 pr-3 font-medium">Outcome</th>
							<th class="py-1 text-right font-medium">Fwd Return</th>
						</tr>
					</thead>
					<tbody>
						{#each evidence.historical_analogs as analog, i (analog.date + analog.symbol + i)}
							<tr class="border-t border-base-800">
								<td class="py-1.5 pr-3 font-mono text-base-300">{analog.date}</td>
								<td class="py-1.5 pr-3 font-mono text-base-200">{analog.symbol}</td>
								<td class="py-1.5 pr-3 text-right font-mono text-accent">
									{(analog.similarity * 100).toFixed(0)}%
								</td>
								<td class="py-1.5 pr-3 text-base-300">{analog.outcome ?? '—'}</td>
								<td
									class="py-1.5 text-right font-mono"
									class:text-long={(analog.forward_return ?? 0) > 0}
									class:text-short={(analog.forward_return ?? 0) < 0}
								>
									{formatReturn(analog.forward_return)}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
</div>
