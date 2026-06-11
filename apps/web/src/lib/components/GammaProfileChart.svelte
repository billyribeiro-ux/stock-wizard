<script lang="ts">
	import * as echarts from 'echarts';
	import type { EChartsOption } from 'echarts';

	interface Props {
		/** Per-strike GEX. Either an explicit map, or derived from a result's `levels`/`meta`. */
		levels?: Record<string, number>;
		meta?: Record<string, unknown>;
		title?: string;
	}

	let { levels = {}, meta = {}, title = 'Gamma Exposure by Strike' }: Props = $props();

	/**
	 * Extract `{ strike, gex }` pairs. Prefer an explicit `meta.gamma_profile`
	 * (array of { strike, gex } or a { strike: gex } map); otherwise pull keys
	 * like `gex_4500` / `gamma@4500` out of `levels`.
	 */
	const profile = $derived.by(() => {
		const fromMeta = meta?.gamma_profile;
		const points: { strike: number; gex: number }[] = [];

		if (Array.isArray(fromMeta)) {
			for (const entry of fromMeta as Array<Record<string, number>>) {
				const strike = Number(entry.strike ?? entry.k);
				const gex = Number(entry.gex ?? entry.value);
				if (!Number.isNaN(strike) && !Number.isNaN(gex)) points.push({ strike, gex });
			}
		} else if (fromMeta && typeof fromMeta === 'object') {
			for (const [k, v] of Object.entries(fromMeta as Record<string, number>)) {
				const strike = Number(k);
				if (!Number.isNaN(strike)) points.push({ strike, gex: Number(v) });
			}
		} else {
			for (const [key, value] of Object.entries(levels)) {
				const match = key.match(/(?:gex|gamma)[_@:]?(-?\d+(?:\.\d+)?)/i);
				if (match) points.push({ strike: Number(match[1]), gex: Number(value) });
			}
		}

		return points.sort((a, b) => a.strike - b.strike);
	});

	const hasData = $derived(profile.length > 0);

	let container = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (!container || !hasData) return;

		const chart = echarts.init(container, 'dark', { renderer: 'canvas' });

		const option: EChartsOption = {
			backgroundColor: 'transparent',
			grid: { left: 56, right: 16, top: 16, bottom: 36 },
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'shadow' },
				valueFormatter: (value) => Number(value).toLocaleString()
			},
			xAxis: {
				type: 'category',
				data: profile.map((p) => p.strike),
				name: 'Strike',
				nameLocation: 'middle',
				nameGap: 26,
				axisLabel: { color: '#9aa6b8' },
				axisLine: { lineStyle: { color: '#353f50' } }
			},
			yAxis: {
				type: 'value',
				name: 'GEX',
				axisLabel: { color: '#9aa6b8' },
				splitLine: { lineStyle: { color: '#161c27' } }
			},
			series: [
				{
					type: 'bar',
					data: profile.map((p) => ({
						value: p.gex,
						itemStyle: { color: p.gex >= 0 ? '#22c55e' : '#ef4444' }
					})),
					barMaxWidth: 28
				}
			]
		};

		chart.setOption(option);

		const resize = () => chart.resize();
		window.addEventListener('resize', resize);

		return () => {
			window.removeEventListener('resize', resize);
			chart.dispose();
		};
	});
</script>

<section class="rounded-lg border border-base-700 bg-base-850 p-4">
	<h3 class="mb-3 text-sm font-semibold text-base-100">{title}</h3>
	{#if hasData}
		<div bind:this={container} class="h-72 w-full"></div>
	{:else}
		<div
			class="flex h-72 w-full items-center justify-center rounded-md border border-dashed border-base-700 text-sm text-base-500"
		>
			No per-strike gamma exposure available for this result.
		</div>
	{/if}
</section>
