<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import EquityCurveChart from '$lib/components/EquityCurveChart.svelte';
	import {
		createForwardTest,
		getForwardTest,
		listForwardTests,
		listForwardScanners
	} from './data.remote';
	import type { ForwardTest, ForwardReport, BacktestMetrics, Promotion, Scanner } from '$lib/types';

	const TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d', '1w'] as const;
	const HISTORY_WINDOWS = ['1y', '2y', '5y', '10y', '20y'] as const;

	// --- Form state ----------------------------------------------------------
	let scannerId = $state('');
	let symbol = $state('SPY');
	let timeframe = $state('1d');
	let history = $state('5y');
	let splitFrac = $state(0.6);

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	// Currently-loaded forward test id (drives the result panel + polling).
	let activeId = $state<string | null>(null);

	function isTerminal(status: string | undefined): boolean {
		const s = status?.toLowerCase();
		return s === 'done' || s === 'error';
	}

	// Poll the active run until it reaches a terminal state. We read the query's
	// `current` value so the effect re-runs as the status changes and stops
	// polling once the run is done/errored.
	$effect(() => {
		const id = activeId;
		if (!id) return;
		const status = getForwardTest(id).current?.status;
		if (isTerminal(status)) return;
		const handle = setInterval(() => {
			getForwardTest(id).refresh();
		}, 1500);
		return () => clearInterval(handle);
	});

	async function submit(scanners: Scanner[]): Promise<void> {
		errorMessage = null;
		const id = scannerId || scanners[0]?.scanner_id;
		if (!id) {
			errorMessage = 'No backtestable scanner available.';
			return;
		}
		if (!symbol.trim()) {
			errorMessage = 'Enter a symbol.';
			return;
		}

		submitting = true;
		try {
			const { backtest_id } = await createForwardTest({
				scanner_id: id,
				symbol: symbol.trim().toUpperCase(),
				timeframe,
				history,
				split_frac: splitFrac
			});
			activeId = backtest_id;
			await listForwardTests().refresh();
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start forward test.';
		} finally {
			submitting = false;
		}
	}

	function loadPast(id: string): void {
		errorMessage = null;
		activeId = id;
	}

	const metricRows: { key: keyof BacktestMetrics; label: string; kind: 'pct' | 'num' | 'ratio' }[] =
		[
			{ key: 'win_rate', label: 'Win Rate', kind: 'pct' },
			{ key: 'profit_factor', label: 'Profit Factor', kind: 'ratio' },
			{ key: 'expectancy', label: 'Expectancy', kind: 'num' },
			{ key: 'total_pnl', label: 'Total P&L', kind: 'num' },
			{ key: 'sharpe', label: 'Sharpe', kind: 'ratio' },
			{ key: 'sortino', label: 'Sortino', kind: 'ratio' },
			{ key: 'max_drawdown', label: 'Max Drawdown', kind: 'pct' },
			{ key: 'cagr', label: 'CAGR', kind: 'pct' },
			{ key: 'total_trades', label: 'Total Trades', kind: 'num' },
			{ key: 'exposure', label: 'Exposure', kind: 'pct' }
		];

	function fmtMetric(value: number | undefined, kind: 'pct' | 'num' | 'ratio'): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		if (kind === 'pct') return `${(value * 100).toFixed(1)}%`;
		if (kind === 'ratio') return value.toFixed(2);
		return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
	}

	function fmtDrift(value: number | undefined, kind: 'pct' | 'num' | 'ratio'): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		const sign = value >= 0 ? '+' : '';
		if (kind === 'pct') return `${sign}${(value * 100).toFixed(1)}%`;
		if (kind === 'ratio') return `${sign}${value.toFixed(2)}`;
		return `${sign}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
	}

	/** A drop in drawdown (more negative delta) is good, so it inverts. */
	function driftTone(key: keyof BacktestMetrics, value: number | undefined): string {
		if (value === undefined || value === null || Number.isNaN(value) || value === 0)
			return 'text-base-400';
		const good = key === 'max_drawdown' ? value < 0 : value > 0;
		return good ? 'text-long' : 'text-short';
	}

	function statusTone(status: string): string {
		const s = status?.toLowerCase();
		if (s === 'done') return 'text-ok';
		if (s === 'error') return 'text-danger';
		return 'text-warn';
	}

	const PROMOTION_META: Record<
		Promotion,
		{ label: string; icon: string; box: string; text: string; dot: string }
	> = {
		promote: {
			label: 'PROMOTE',
			icon: 'seal-check',
			box: 'border-ok/40 bg-ok/10',
			text: 'text-ok',
			dot: 'bg-ok'
		},
		keep_testing: {
			label: 'KEEP TESTING',
			icon: 'flask',
			box: 'border-warn/40 bg-warn/10',
			text: 'text-warn',
			dot: 'bg-warn'
		},
		retire: {
			label: 'RETIRE',
			icon: 'prohibit',
			box: 'border-danger/40 bg-danger/10',
			text: 'text-danger',
			dot: 'bg-danger'
		}
	};

	function promotionMeta(p: Promotion) {
		return (
			PROMOTION_META[p] ?? {
				label: String(p ?? 'unknown').toUpperCase(),
				icon: 'question',
				box: 'border-base-700 bg-base-850',
				text: 'text-base-200',
				dot: 'bg-base-500'
			}
		);
	}

	function isForwardReport(result: unknown): result is ForwardReport {
		return !!result && typeof result === 'object' && 'promotion' in result;
	}
</script>

<svelte:head>
	<title>Forward Test Lab · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="test-tube" class="text-accent" />
			Forward Test Lab
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Split history into in-sample and out-of-sample windows to decide whether a strategy earns
			promotion to live testing.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[20rem_1fr]">
		<!-- Config + past runs column -->
		<div class="space-y-6">
			<!-- Config form -->
			{#snippet configForm(scanners: Scanner[])}
				<section class="space-y-4 rounded-lg border border-base-700 bg-base-850 p-5">
					<h2 class="text-xs font-medium tracking-wide text-base-400 uppercase">Configuration</h2>

					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">Scanner</span>
						<select
							bind:value={scannerId}
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
						>
							{#each scanners as scanner (scanner.scanner_id)}
								<option value={scanner.scanner_id}>{scanner.name}</option>
							{:else}
								<option value="" disabled>No backtestable scanners</option>
							{/each}
						</select>
					</label>

					<div class="grid grid-cols-2 gap-3">
						<label class="block">
							<span class="mb-1 block text-xs font-medium text-base-300">Symbol</span>
							<input
								type="text"
								bind:value={symbol}
								placeholder="SPY"
								class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
							/>
						</label>
						<label class="block">
							<span class="mb-1 block text-xs font-medium text-base-300">Timeframe</span>
							<select
								bind:value={timeframe}
								class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
							>
								{#each TIMEFRAMES as tf (tf)}
									<option value={tf}>{tf}</option>
								{/each}
							</select>
						</label>
					</div>

					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">History</span>
						<select
							bind:value={history}
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
						>
							{#each HISTORY_WINDOWS as hw (hw)}
								<option value={hw}>{hw}</option>
							{/each}
						</select>
					</label>

					<div class="border-t border-base-800 pt-4">
						<h3 class="mb-2 flex items-center gap-1.5 text-xs font-medium text-base-300">
							<Icon name="sliders-horizontal" />
							Split
						</h3>
						<label class="block">
							<div class="mb-1 flex items-center justify-between text-xs text-base-400">
								<span>In-sample fraction</span>
								<span class="font-mono text-base-200">{(splitFrac * 100).toFixed(0)}%</span>
							</div>
							<input
								type="range"
								min="0.4"
								max="0.8"
								step="0.05"
								bind:value={splitFrac}
								class="w-full accent-accent"
							/>
							<div class="mt-1 flex items-center justify-between text-[11px] text-base-500">
								<span>train {(splitFrac * 100).toFixed(0)}%</span>
								<span>test {((1 - splitFrac) * 100).toFixed(0)}%</span>
							</div>
						</label>
					</div>

					{#if errorMessage}
						<p class="flex items-center gap-1.5 text-sm text-danger">
							<Icon name="warning-circle" />
							{errorMessage}
						</p>
					{/if}

					<button
						type="button"
						onclick={() => submit(scanners)}
						disabled={submitting}
						class="flex w-full items-center justify-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
					>
						{#if submitting}
							<Icon name="spinner-gap" class="animate-spin" />
							Enqueuing…
						{:else}
							<Icon name="play" />
							Run Forward Test
						{/if}
					</button>
				</section>
			{/snippet}

			<svelte:boundary>
				{#snippet pending()}
					<div class="h-80 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
				{/snippet}
				{@render configForm(await listForwardScanners())}
				{#snippet failed(error, reset)}
					<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
						<Icon name="warning-circle" class="text-2xl text-danger" />
						<p class="mt-2 text-sm text-base-200">
							{error instanceof Error ? error.message : 'Failed to load scanners.'}
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

			<!-- Past forward tests -->
			<section class="rounded-lg border border-base-700 bg-base-850 p-4">
				<header class="mb-3 flex items-center justify-between">
					<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
						<Icon name="clock-counter-clockwise" class="text-accent" />
						Past forward tests
					</h2>
					<button
						type="button"
						onclick={() => listForwardTests().refresh()}
						class="flex items-center gap-1 text-xs text-base-400 hover:text-base-200"
					>
						<Icon name="clock-clockwise" />
						refresh
					</button>
				</header>

				<svelte:boundary>
					{#snippet pending()}
						<div class="h-24 animate-pulse rounded-md bg-base-900"></div>
					{/snippet}

					{#await listForwardTests() then { items }}
						{#if items.length === 0}
							<p class="text-xs text-base-500">No forward tests yet.</p>
						{:else}
							<ul class="space-y-2">
								{#each items as item (item.backtest_id)}
									<li>
										<button
											type="button"
											onclick={() => loadPast(item.backtest_id)}
											class="w-full rounded-md border p-2.5 text-left transition-colors"
											class:border-accent={activeId === item.backtest_id}
											class:border-base-700={activeId !== item.backtest_id}
											class:hover:border-base-600={activeId !== item.backtest_id}
										>
											<div class="flex items-center justify-between gap-2">
												<span class="truncate text-xs font-medium text-base-100">
													{item.scanner_id}
												</span>
												<span class="text-[11px] font-medium {statusTone(item.status)}">
													{item.status}
												</span>
											</div>
											<div class="mt-1 flex items-center gap-3 text-[11px] text-base-500">
												<span>{item.timeframe}</span>
												<span class="truncate">{item.universe.join(', ')}</span>
											</div>
										</button>
									</li>
								{/each}
							</ul>
						{/if}
					{/await}
				</svelte:boundary>
			</section>
		</div>

		<!-- Result panel -->
		<div class="min-w-0">
			{#if !activeId}
				<div
					class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-base-700 text-base-400"
				>
					<Icon name="test-tube" class="text-3xl" />
					<p>Run a forward test or pick a past run to inspect its verdict.</p>
				</div>
			{:else}
				{#snippet resultPanel(ft: ForwardTest)}
					{#if !isTerminal(ft.status)}
						<div
							class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-base-700 bg-base-850 text-base-300"
						>
							<Icon name="spinner-gap" class="animate-spin text-3xl text-accent" />
							<p class="text-sm">
								Forward test <span class="font-medium {statusTone(ft.status)}">{ft.status}</span>…
							</p>
							<p class="font-mono text-xs text-base-500">{ft.backtest_id}</p>
						</div>
					{:else if ft.status.toLowerCase() === 'error'}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">{ft.error ?? 'Forward test failed.'}</p>
						</div>
					{:else if !isForwardReport(ft.result)}
						<div class="rounded-lg border border-warn/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-warn" />
							<p class="mt-2 text-sm text-base-200">
								This run does not contain a forward-test report.
							</p>
						</div>
					{:else}
						{@const report = ft.result}
						{@const promo = promotionMeta(report.promotion)}
						{@const mc = report.monte_carlo}
						{@const probProfit = mc?.prob_profit ?? 0}
						<div class="space-y-6">
							<!-- Header -->
							<div
								class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-base-700 bg-base-850 px-4 py-3"
							>
								<div>
									<div class="flex items-center gap-2 text-sm font-semibold text-base-100">
										<Icon name="crosshair" class="text-accent" />
										{ft.scanner_id}
									</div>
									<div class="mt-0.5 flex items-center gap-3 text-xs text-base-500">
										<span>{ft.timeframe}</span>
										<span>{ft.universe.join(', ')}</span>
										<span class="font-mono">{report.period_start} → {report.period_end}</span>
									</div>
								</div>
								<span class="flex items-center gap-1.5 text-sm font-medium {statusTone(ft.status)}">
									<Icon name="circle" />
									{ft.status}
								</span>
							</div>

							<!-- Promotion badge + rationale -->
							<section class="rounded-lg border {promo.box} p-5">
								<div class="flex items-center gap-3">
									<Icon name={promo.icon} class="text-3xl {promo.text}" />
									<div>
										<div class="text-[11px] font-medium tracking-widest text-base-400 uppercase">
											Verdict
										</div>
										<div class="text-2xl font-bold {promo.text}">{promo.label}</div>
									</div>
								</div>
								{#if report.rationale}
									<p class="mt-3 text-sm text-base-200">{report.rationale}</p>
								{/if}
							</section>

							<!-- Baseline vs forward metrics with drift -->
							<section class="rounded-lg border border-base-700 bg-base-850 p-4">
								<h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
									<Icon name="arrows-left-right" class="text-accent" />
									In-sample vs Out-of-sample
								</h3>
								<div class="overflow-x-auto">
									<table class="w-full text-sm">
										<thead>
											<tr class="text-left text-base-500">
												<th class="py-1.5 pr-3 font-medium">Metric</th>
												<th class="py-1.5 pr-3 text-right font-medium">Baseline</th>
												<th class="py-1.5 pr-3 text-right font-medium">Forward</th>
												<th class="py-1.5 text-right font-medium">Drift</th>
											</tr>
										</thead>
										<tbody>
											{#each metricRows as row (row.key)}
												<tr class="border-t border-base-800">
													<td class="py-1.5 pr-3 text-base-300">{row.label}</td>
													<td class="py-1.5 pr-3 text-right font-mono text-base-200">
														{fmtMetric(report.baseline?.[row.key], row.kind)}
													</td>
													<td class="py-1.5 pr-3 text-right font-mono text-base-50">
														{fmtMetric(report.forward?.[row.key], row.kind)}
													</td>
													<td
														class="py-1.5 text-right font-mono {driftTone(
															row.key,
															report.drift?.[row.key]
														)}"
													>
														{fmtDrift(report.drift?.[row.key], row.kind)}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</section>

							<!-- Monte-Carlo panel -->
							<section class="rounded-lg border border-base-700 bg-base-850 p-4">
								<h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
									<Icon name="dice-five" class="text-accent" />
									Monte-Carlo simulation
								</h3>
								<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
									<div class="rounded-lg border border-base-700 bg-base-900 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">Prob Profit</div>
										<div
											class="mt-1 font-mono text-lg font-semibold"
											class:text-long={probProfit >= 0.5}
											class:text-short={probProfit < 0.5}
										>
											{fmtMetric(mc?.prob_profit, 'pct')}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-900 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">P05 Return</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtMetric(mc?.p05_return, 'pct')}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-900 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">
											Median Return
										</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtMetric(mc?.median_return, 'pct')}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-900 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">P95 Return</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtMetric(mc?.p95_return, 'pct')}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-900 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">
											Median Max DD
										</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtMetric(mc?.median_max_dd, 'pct')}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-900 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">
											Worst Max DD
										</div>
										<div class="mt-1 font-mono text-lg font-semibold text-short">
											{fmtMetric(mc?.worst_max_dd, 'pct')}
										</div>
									</div>
								</div>
							</section>

							<!-- Walk-forward mini-table -->
							<section class="rounded-lg border border-base-700 bg-base-850 p-4">
								<h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
									<Icon name="stack" class="text-accent" />
									Walk-forward
									<span class="text-xs font-normal text-base-500">
										({report.walk_forward?.length ?? 0} splits)
									</span>
								</h3>
								{#if !report.walk_forward || report.walk_forward.length === 0}
									<p class="text-xs text-base-500">No walk-forward splits.</p>
								{:else}
									<div class="overflow-x-auto">
										<table class="w-full text-xs">
											<thead>
												<tr class="text-left text-base-500">
													<th class="py-1.5 pr-3 font-medium">Split</th>
													<th class="py-1.5 pr-3 font-medium">Period</th>
													<th class="py-1.5 pr-3 text-right font-medium">Win Rate</th>
													<th class="py-1.5 pr-3 text-right font-medium">Profit Factor</th>
													<th class="py-1.5 pr-3 text-right font-medium">Sharpe</th>
													<th class="py-1.5 pr-3 text-right font-medium">Max DD</th>
													<th class="py-1.5 text-right font-medium">Trades</th>
												</tr>
											</thead>
											<tbody>
												{#each report.walk_forward as split (split.split)}
													<tr class="border-t border-base-800">
														<td class="py-1.5 pr-3 font-mono text-base-300">#{split.split}</td>
														<td class="py-1.5 pr-3 font-mono whitespace-nowrap text-base-400">
															{split.period_start} → {split.period_end}
														</td>
														<td class="py-1.5 pr-3 text-right font-mono text-base-200">
															{fmtMetric(split.metrics?.win_rate, 'pct')}
														</td>
														<td class="py-1.5 pr-3 text-right font-mono text-base-200">
															{fmtMetric(split.metrics?.profit_factor, 'ratio')}
														</td>
														<td class="py-1.5 pr-3 text-right font-mono text-base-200">
															{fmtMetric(split.metrics?.sharpe, 'ratio')}
														</td>
														<td class="py-1.5 pr-3 text-right font-mono text-base-200">
															{fmtMetric(split.metrics?.max_drawdown, 'pct')}
														</td>
														<td class="py-1.5 text-right font-mono text-base-200">
															{split.metrics?.total_trades ?? '—'}
														</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{/if}
							</section>

							<!-- Out-of-sample equity curve -->
							<EquityCurveChart
								points={report.equity_curve ?? []}
								title="Out-of-sample Equity Curve"
							/>
						</div>
					{/if}
				{/snippet}

				<svelte:boundary>
					{#snippet pending()}
						<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
					{/snippet}
					{@render resultPanel(await getForwardTest(activeId))}
					{#snippet failed(error, reset)}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">
								{error instanceof Error ? error.message : 'Failed to load forward test.'}
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
	</div>
</div>
