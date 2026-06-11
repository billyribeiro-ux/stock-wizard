<script lang="ts">
	import Icon from './Icon.svelte';
	import type { ScannerResult } from '$lib/types';

	interface Props {
		results: ScannerResult[];
		onselect?: (result: ScannerResult) => void;
	}

	let { results, onselect }: Props = $props();

	type SortKey = 'symbol' | 'timeframe' | 'direction' | 'score' | 'classification' | 'ts';

	let sortKey = $state<SortKey>('score');
	let sortDir = $state<'asc' | 'desc'>('desc');

	function toggleSort(key: SortKey): void {
		if (sortKey === key) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = key;
			sortDir = key === 'symbol' || key === 'timeframe' ? 'asc' : 'desc';
		}
	}

	function valueFor(result: ScannerResult, key: SortKey): string | number {
		switch (key) {
			case 'score':
				return result.score ?? 0;
			case 'ts':
				return new Date(result.ts).getTime() || 0;
			case 'direction':
				return result.direction ?? '';
			default:
				return (result[key] as string) ?? '';
		}
	}

	const sorted = $derived(
		[...results].sort((a, b) => {
			const av = valueFor(a, sortKey);
			const bv = valueFor(b, sortKey);
			const cmp =
				typeof av === 'number' && typeof bv === 'number'
					? av - bv
					: String(av).localeCompare(String(bv));
			return sortDir === 'asc' ? cmp : -cmp;
		})
	);

	const columns: { key: SortKey; label: string; align?: string }[] = [
		{ key: 'symbol', label: 'Symbol' },
		{ key: 'timeframe', label: 'TF' },
		{ key: 'direction', label: 'Dir' },
		{ key: 'score', label: 'Score', align: 'text-right' },
		{ key: 'classification', label: 'Classification' },
		{ key: 'ts', label: 'Time', align: 'text-right' }
	];

	function directionTone(direction: string | undefined): string {
		if (direction === 'LONG') return 'text-long';
		if (direction === 'SHORT') return 'text-short';
		return 'text-neutral-signal';
	}

	function time(iso: string): string {
		const date = new Date(iso);
		return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
	}
</script>

<div class="overflow-x-auto rounded-lg border border-base-700">
	<table class="w-full border-collapse text-sm">
		<thead>
			<tr class="bg-base-850 text-left text-xs tracking-wide text-base-400 uppercase">
				{#each columns as col (col.key)}
					<th class="px-3 py-2 font-medium {col.align ?? ''}">
						<button
							type="button"
							class="inline-flex items-center gap-1 hover:text-base-100"
							onclick={() => toggleSort(col.key)}
						>
							{col.label}
							{#if sortKey === col.key}
								<Icon name={sortDir === 'asc' ? 'caret-up' : 'caret-down'} />
							{:else}
								<Icon name="arrows-down-up" class="opacity-30" />
							{/if}
						</button>
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each sorted as result (result.id ?? result.symbol + result.ts + result.scanner_id)}
				<tr
					class="cursor-pointer border-t border-base-800 transition-colors hover:bg-base-850"
					onclick={() => onselect?.(result)}
				>
					<td class="px-3 py-2 font-mono font-semibold text-base-100">
						<span class="flex items-center gap-1.5">
							{#if result.triggered}
								<Icon name="lightning" class="text-accent" label="triggered" />
							{/if}
							{result.symbol}
						</span>
					</td>
					<td class="px-3 py-2 text-base-300">{result.timeframe}</td>
					<td class="px-3 py-2 font-medium {directionTone(result.direction)}">
						{result.direction ?? '—'}
					</td>
					<td class="px-3 py-2 text-right font-mono">
						<span class="text-accent">{(result.score * 100).toFixed(0)}</span>
					</td>
					<td class="px-3 py-2 text-base-200">{result.classification}</td>
					<td class="px-3 py-2 text-right text-xs text-base-400">{time(result.ts)}</td>
				</tr>
			{:else}
				<tr>
					<td colspan={columns.length} class="px-3 py-8 text-center text-base-400">
						No results yet.
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
