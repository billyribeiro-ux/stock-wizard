<script lang="ts">
	import * as echarts from 'echarts';
	import type { EChartsOption } from 'echarts';

	interface Props {
		/** Feature name → importance value. */
		importance?: Record<string, number>;
		title?: string;
	}

	let { importance = {}, title = 'Feature Importance' }: Props = $props();

	/** Sort ascending so the largest bar sits at the top of a horizontal chart. */
	const features = $derived(
		Object.entries(importance)
			.map(([name, value]) => ({ name, value: Number(value) }))
			.filter((f) => !Number.isNaN(f.value))
			.sort((a, b) => a.value - b.value)
	);

	const hasData = $derived(features.length > 0);

	let container = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (!container || !hasData) return;

		const chart = echarts.init(container, 'dark', { renderer: 'canvas' });

		const option: EChartsOption = {
			backgroundColor: 'transparent',
			grid: { left: 8, right: 24, top: 16, bottom: 36, containLabel: true },
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'shadow' },
				valueFormatter: (value) => Number(value).toFixed(4)
			},
			xAxis: {
				type: 'value',
				axisLabel: { color: '#9aa6b8' },
				axisLine: { lineStyle: { color: '#353f50' } },
				splitLine: { lineStyle: { color: '#161c27' } }
			},
			yAxis: {
				type: 'category',
				data: features.map((f) => f.name),
				axisLabel: { color: '#9aa6b8' },
				axisLine: { lineStyle: { color: '#353f50' } }
			},
			series: [
				{
					type: 'bar',
					data: features.map((f) => f.value),
					itemStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
							{ offset: 0, color: 'rgba(34,197,94,0.25)' },
							{ offset: 1, color: '#22c55e' }
						])
					},
					barMaxWidth: 18
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
		<div bind:this={container} class="h-80 w-full"></div>
	{:else}
		<div
			class="flex h-80 w-full items-center justify-center rounded-md border border-dashed border-base-700 text-sm text-base-500"
		>
			No feature importance available for this model.
		</div>
	{/if}
</section>
