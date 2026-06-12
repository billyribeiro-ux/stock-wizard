<script lang="ts">
	import * as echarts from 'echarts';
	import type { EChartsOption } from 'echarts';
	import type { EquityPoint } from '$lib/types';

	interface Props {
		points?: EquityPoint[];
		title?: string;
	}

	let { points = [], title = 'Equity Curve' }: Props = $props();

	const hasData = $derived(points.length > 0);

	let container = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (!container || !hasData) return;

		const chart = echarts.init(container, 'dark', { renderer: 'canvas' });

		const option: EChartsOption = {
			backgroundColor: 'transparent',
			grid: { left: 64, right: 16, top: 16, bottom: 36 },
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'line' },
				valueFormatter: (value) => Number(value).toLocaleString()
			},
			xAxis: {
				type: 'category',
				data: points.map((p) => p.ts),
				boundaryGap: false,
				axisLabel: { color: '#9aa6b8', hideOverlap: true },
				axisLine: { lineStyle: { color: '#353f50' } }
			},
			yAxis: {
				type: 'value',
				name: 'Equity',
				scale: true,
				axisLabel: { color: '#9aa6b8' },
				splitLine: { lineStyle: { color: '#161c27' } }
			},
			series: [
				{
					type: 'line',
					data: points.map((p) => p.equity),
					showSymbol: false,
					lineStyle: { color: '#22c55e', width: 2 },
					areaStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
							{ offset: 0, color: 'rgba(34,197,94,0.30)' },
							{ offset: 1, color: 'rgba(34,197,94,0.02)' }
						])
					}
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
			No equity curve available for this backtest.
		</div>
	{/if}
</section>
