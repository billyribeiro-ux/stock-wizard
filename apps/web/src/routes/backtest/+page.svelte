<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import EquityCurveChart from '$lib/components/EquityCurveChart.svelte';
	import { createBacktest, getBacktest, listBacktests, listBacktestableScanners } from './data.remote';
	import type { Backtest, BacktestMetrics, Scanner, TradeRecord } from '$lib/types';

	const TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d', '1w'] as const;
	const HISTORY_WINDOWS = ['1y', '2y', '5y', '10y', '20y'] as const;

	// --- Form state ----------------------------------------------------------
	let scannerId = $state('');
	let symbol = $state('SPY');
	let timeframe = $state('1d');
	let history = $state('5y');
	let minScore = $state(0.6);
	let stopAtr = $state(2);
	let allowShort = $state(false);

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	// Currently-loaded backtest id (drives the result panel + polling).
	let activeId = $state<string | null>(null);

	function isTerminal(status: string | undefined): boolean {
		const s = status?.toLowerCase();
		return s === 'done' || s === 'error';
	}

	// Poll the active backtest until it reaches a terminal state. We read the
	// query's `current` value so the effect re-runs as the status changes and
	// stops polling once the run is done/errored.
	$effect(() => {
		const id = activeId;
		if (!id) return;
		const status = getBacktest(id).current?.status;
		if (isTerminal(status)) return;
		const handle = setInterval(() => {
			getBacktest(id).refresh();
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
			const { backtest_id } = await createBacktest({
				scanner_id: id,
				symbol: symbol.trim().toUpperCase(),
				timeframe,
				history,
				params: {
					min_score: minScore,
					stop_atr: stopAtr,
					allow_short: allowShort
				}
			});
			activeId = backtest_id;
			await listBacktests().refresh();
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start backtest.';
		} finally {
			submitting = false;
		}
	}

	function loadPast(id: string): void {
		errorMessage = null;
		activeId = id;
	}

	const metricCards: { key: keyof BacktestMetrics; label: string; kind: 'pct' | 'num' | 'ratio' }[] =
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

	function fmtTs(ts: string): string {
		const d = new Date(ts);
		return Number.isNaN(d.getTime()) ? ts : d.toLocaleString();
	}

	function fmtPrice(value: number): string {
		return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
	}

	function fmtPct(value: number): string {
		return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
	}

	function statusTone(status: string): string {
		const s = status?.toLowerCase();
		if (s === 'done') return 'text-ok';
		if (s === 'error') return 'text-danger';
		return 'text-warn';
	}

	function sideTone(side: string): string {
		return side === 'SHORT' ? 'text-short' : 'text-long';
	}
</script>

<svelte:head>
	<title>Backtest Lab · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="flask" class="text-accent" />
			Backtest Lab
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Replay a backtestable scanner over historical data and inspect its performance.
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
							Parameters
						</h3>
						<div class="grid grid-cols-2 gap-3">
							<label class="block">
								<span class="mb-1 block text-xs text-base-400">Min Score</span>
								<input
									type="number"
									step="0.05"
									min="0"
									max="1"
									bind:value={minScore}
									class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
								/>
							</label>
							<label class="block">
								<span class="mb-1 block text-xs text-base-400">Stop (ATR)</span>
								<input
									type="number"
									step="0.5"
									min="0"
									bind:value={stopAtr}
									class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
								/>
							</label>
						</div>
						<label class="mt-3 flex items-center gap-2 text-sm text-base-300">
							<input
								type="checkbox"
								bind:checked={allowShort}
								class="h-4 w-4 rounded border-base-700 bg-base-900 accent-accent"
							/>
							Allow short trades
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
							Run Backtest
						{/if}
					</button>
				</section>
			{/snippet}

			<svelte:boundary>
				{#snippet pending()}
					<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
				{/snippet}
				{@render configForm(await listBacktestableScanners())}
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

			<!-- Past backtests -->
			<section class="rounded-lg border border-base-700 bg-base-850 p-4">
				<header class="mb-3 flex items-center justify-between">
					<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
						<Icon name="clock-counter-clockwise" class="text-accent" />
						Past backtests
					</h2>
					<button
						type="button"
						onclick={() => listBacktests().refresh()}
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

					{#await listBacktests() then { items }}
						{#if items.length === 0}
							<p class="text-xs text-base-500">No backtests yet.</p>
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
											{#if item.metrics}
												<div class="mt-1 flex items-center gap-3 font-mono text-[11px] text-base-400">
													<span>WR {fmtMetric(item.metrics.win_rate, 'pct')}</span>
													<span>PF {fmtMetric(item.metrics.profit_factor, 'ratio')}</span>
													<span>n {item.metrics.total_trades}</span>
												</div>
											{/if}
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
					<Icon name="flask" class="text-3xl" />
					<p>Run a backtest or pick a past run to inspect its results.</p>
				</div>
			{:else}
				{#snippet resultPanel(bt: Backtest)}
					{#if !isTerminal(bt.status)}
						<div
							class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-base-700 bg-base-850 text-base-300"
						>
							<Icon name="spinner-gap" class="animate-spin text-3xl text-accent" />
							<p class="text-sm">
								Backtest <span class="font-medium {statusTone(bt.status)}">{bt.status}</span>…
							</p>
							<p class="font-mono text-xs text-base-500">{bt.backtest_id}</p>
						</div>
					{:else if bt.status.toLowerCase() === 'error'}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">{bt.error ?? 'Backtest failed.'}</p>
						</div>
					{:else}
						{@const metrics = bt.result?.metrics ?? bt.metrics}
						{@const trades = bt.result?.trades ?? []}
						<div class="space-y-6">
							<div
								class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-base-700 bg-base-850 px-4 py-3"
							>
								<div>
									<div class="flex items-center gap-2 text-sm font-semibold text-base-100">
										<Icon name="crosshair" class="text-accent" />
										{bt.scanner_id}
									</div>
									<div class="mt-0.5 flex items-center gap-3 text-xs text-base-500">
										<span>{bt.timeframe}</span>
										<span>{bt.universe.join(', ')}</span>
										{#if bt.result}
											<span class="font-mono">
												{bt.result.period_start} → {bt.result.period_end}
											</span>
										{/if}
									</div>
								</div>
								<span class="flex items-center gap-1.5 text-sm font-medium {statusTone(bt.status)}">
									<Icon name="circle" />
									{bt.status}
								</span>
							</div>

							<!-- Metric stat cards -->
							{#if metrics}
								<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
									{#each metricCards as card (card.key)}
										<div class="rounded-lg border border-base-700 bg-base-850 p-3">
											<div class="text-[11px] tracking-wide text-base-500 uppercase">{card.label}</div>
											<div class="mt-1 font-mono text-lg font-semibold text-base-50">
												{fmtMetric(metrics[card.key] as number, card.kind)}
											</div>
										</div>
									{/each}
								</div>
							{/if}

							<!-- Equity curve -->
							<EquityCurveChart points={bt.result?.equity_curve ?? []} />

							<!-- Trades table -->
							<section class="rounded-lg border border-base-700 bg-base-850 p-4">
								<h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
									<Icon name="list-checks" class="text-accent" />
									Trades
									<span class="text-xs font-normal text-base-500">({trades.length})</span>
								</h3>
								{#if trades.length === 0}
									<p class="text-xs text-base-500">No trades were taken.</p>
								{:else}
									<div class="overflow-x-auto">
										<table class="w-full text-xs">
											<thead>
												<tr class="text-left text-base-500">
													<th class="py-1.5 pr-3 font-medium">Entry</th>
													<th class="py-1.5 pr-3 font-medium">Exit</th>
													<th class="py-1.5 pr-3 font-medium">Side</th>
													<th class="py-1.5 pr-3 text-right font-medium">Entry Px</th>
													<th class="py-1.5 pr-3 text-right font-medium">Exit Px</th>
													<th class="py-1.5 pr-3 text-right font-medium">P&L</th>
													<th class="py-1.5 pr-3 text-right font-medium">Return</th>
													<th class="py-1.5 font-medium">Reason</th>
												</tr>
											</thead>
											<tbody>
												{#each trades as trade, i (trade.entry_ts + trade.symbol + i)}
													{@const t = trade as TradeRecord}
													<tr class="border-t border-base-800">
														<td class="py-1.5 pr-3 font-mono whitespace-nowrap text-base-300">
															{fmtTs(t.entry_ts)}
														</td>
														<td class="py-1.5 pr-3 font-mono whitespace-nowrap text-base-300">
															{fmtTs(t.exit_ts)}
														</td>
														<td class="py-1.5 pr-3 font-medium {sideTone(t.side)}">{t.side}</td>
														<td class="py-1.5 pr-3 text-right font-mono text-base-200">
															{fmtPrice(t.entry_price)}
														</td>
														<td class="py-1.5 pr-3 text-right font-mono text-base-200">
															{fmtPrice(t.exit_price)}
														</td>
														<td
															class="py-1.5 pr-3 text-right font-mono"
															class:text-long={t.pnl > 0}
															class:text-short={t.pnl < 0}
														>
															{fmtPrice(t.pnl)}
														</td>
														<td
															class="py-1.5 pr-3 text-right font-mono"
															class:text-long={t.return_pct > 0}
															class:text-short={t.return_pct < 0}
														>
															{fmtPct(t.return_pct)}
														</td>
														<td class="py-1.5 text-base-400">{t.exit_reason}</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{/if}
							</section>
						</div>
					{/if}
				{/snippet}

				<svelte:boundary>
					{#snippet pending()}
						<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
					{/snippet}
					{@render resultPanel(await getBacktest(activeId))}
					{#snippet failed(error, reset)}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">
								{error instanceof Error ? error.message : 'Failed to load backtest.'}
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
