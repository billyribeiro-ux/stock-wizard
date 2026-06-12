<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import EquityCurveChart from '$lib/components/EquityCurveChart.svelte';
	import { getBacktest, listReplayableBacktests } from './data.remote';
	import type { BacktestSummary, Side } from '$lib/types';

	// --- Replay state ----------------------------------------------------------
	let selectedId = $state('');
	let step = $state(0);
	let playing = $state(false);

	const backtestQuery = $derived(selectedId ? getBacktest(selectedId) : null);
	const backtest = $derived(backtestQuery?.current);
	const trades = $derived(backtest?.result?.trades ?? []);
	const total = $derived(trades.length);
	/** step clamped to the loaded trade list, so a stale index can never overflow */
	const index = $derived(total === 0 ? 0 : Math.min(step, total - 1));
	const trade = $derived(total > 0 ? trades[index] : undefined);
	const curve = $derived(backtest?.result?.equity_curve ?? []);

	/** Equity points up to the current trade's exit, so the curve "draws" while stepping. */
	const visibleCurve = $derived.by(() => {
		if (!trade) return [];
		const cutoff = new Date(trade.exit_ts).getTime();
		if (Number.isNaN(cutoff)) return curve;
		return curve.filter((p) => {
			const ts = new Date(p.ts).getTime();
			return Number.isNaN(ts) ? true : ts <= cutoff;
		});
	});

	// Running totals over trades replayed so far.
	const completed = $derived(trades.slice(0, index + 1));
	const cumulativePnl = $derived(completed.reduce((sum, t) => sum + t.pnl, 0));
	const winRate = $derived(
		completed.length > 0 ? completed.filter((t) => t.pnl > 0).length / completed.length : 0
	);

	function select(id: string): void {
		selectedId = id;
		step = 0;
		playing = false;
	}

	function prev(): void {
		playing = false;
		if (index > 0) step = index - 1;
	}

	function next(): void {
		playing = false;
		if (index < total - 1) step = index + 1;
	}

	// Auto-step while playing; the interval is torn down whenever playback stops,
	// the trade count changes, or the component unmounts.
	$effect(() => {
		if (!playing || total === 0) return;
		const handle = setInterval(() => {
			if (step >= total - 1) {
				playing = false;
				return;
			}
			step += 1;
		}, 800);
		return () => clearInterval(handle);
	});

	function onKeydown(event: KeyboardEvent): void {
		const target = event.target as HTMLElement | null;
		if (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return;
		if (event.key === 'ArrowLeft') {
			event.preventDefault();
			prev();
		} else if (event.key === 'ArrowRight') {
			event.preventDefault();
			next();
		}
	}

	// --- Formatting ------------------------------------------------------------
	function fmtTs(ts: string): string {
		const d = new Date(ts);
		return Number.isNaN(d.getTime()) ? ts : d.toLocaleString();
	}

	function fmtPrice(value: number): string {
		return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
	}

	function fmtSigned(value: number): string {
		return `${value >= 0 ? '+' : ''}${fmtPrice(value)}`;
	}

	function fmtPct(value: number): string {
		return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
	}

	function fmtMetric(value: number | undefined, kind: 'pct' | 'ratio'): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return kind === 'pct' ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
	}

	function sideMeta(side: Side): { tone: string; bg: string; icon: string } {
		if (side === 'LONG') return { tone: 'text-long', bg: 'bg-long-soft', icon: 'trend-up' };
		if (side === 'SHORT') return { tone: 'text-short', bg: 'bg-short-soft', icon: 'trend-down' };
		return { tone: 'text-neutral-signal', bg: 'bg-base-800', icon: 'minus' };
	}
</script>

<svelte:window onkeydown={onKeydown} />

<svelte:head>
	<title>Trade Replay · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="play-circle" class="text-accent" />
			Trade Replay
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Step through a finished backtest trade-by-trade and watch the equity curve build.
			<span class="ml-1 inline-flex items-center gap-1 text-xs text-base-500">
				<Icon name="keyboard" />
				use ← / → to step
			</span>
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[20rem_1fr]">
		<!-- Backtest picker -->
		<section class="self-start rounded-lg border border-base-700 bg-base-850 p-4">
			<header class="mb-3 flex items-center justify-between">
				<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
					<Icon name="flask" class="text-accent" />
					Finished backtests
				</h2>
				<button
					type="button"
					onclick={() => listReplayableBacktests().refresh()}
					class="flex items-center gap-1 text-xs text-base-400 hover:text-base-200"
				>
					<Icon name="clock-clockwise" />
					refresh
				</button>
			</header>

			{#snippet backtestList(items: BacktestSummary[])}
				{#if items.length === 0}
					<p class="text-xs text-base-500">
						No finished backtests yet. Run one in the Backtest Lab first.
					</p>
				{:else}
					<ul class="space-y-2">
						{#each items as item (item.backtest_id)}
							<li>
								<button
									type="button"
									onclick={() => select(item.backtest_id)}
									class="w-full rounded-md border p-2.5 text-left transition-colors"
									class:border-accent={selectedId === item.backtest_id}
									class:border-base-700={selectedId !== item.backtest_id}
									class:hover:border-base-600={selectedId !== item.backtest_id}
								>
									<div class="flex items-center justify-between gap-2">
										<span class="truncate text-xs font-medium text-base-100">
											{item.scanner_id}
										</span>
										<span class="text-[11px] font-medium text-ok">{item.status}</span>
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
			{/snippet}

			<svelte:boundary>
				{#snippet pending()}
					<div class="h-24 animate-pulse rounded-md bg-base-900"></div>
				{/snippet}

				{@render backtestList(await listReplayableBacktests())}

				{#snippet failed(error, reset)}
					<div class="p-2 text-center text-xs">
						<p class="text-base-200">
							{error instanceof Error ? error.message : 'Failed to load backtests.'}
						</p>
						<button
							type="button"
							onclick={reset}
							class="mt-2 rounded-md bg-base-800 px-3 py-1.5 text-base-200"
						>
							retry
						</button>
					</div>
				{/snippet}
			</svelte:boundary>
		</section>

		<!-- Replay panel -->
		<div class="min-w-0">
			{#if !selectedId}
				<div
					class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-base-700 text-base-400"
				>
					<Icon name="play-circle" class="text-3xl" />
					<p>Pick a finished backtest to replay its trades.</p>
				</div>
			{:else if backtestQuery?.error}
				<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
					<Icon name="warning-circle" class="text-2xl text-danger" />
					<p class="mt-2 text-sm text-base-200">
						{backtestQuery.error instanceof Error
							? backtestQuery.error.message
							: 'Failed to load backtest.'}
					</p>
					<button
						type="button"
						onclick={() => backtestQuery?.refresh()}
						class="mt-3 rounded-md bg-base-800 px-3 py-1.5 text-xs text-base-200"
					>
						retry
					</button>
				</div>
			{:else if !backtest}
				<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
			{:else if !trade}
				<div
					class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-base-700 text-base-400"
				>
					<Icon name="warning-circle" class="text-3xl" />
					<p>This backtest produced no trades to replay.</p>
				</div>
			{:else}
				<div class="space-y-6">
					<!-- Transport controls -->
					<section
						class="flex flex-wrap items-center gap-4 rounded-lg border border-base-700 bg-base-850 px-4 py-3"
					>
						<div class="flex items-center gap-2">
							<button
								type="button"
								onclick={prev}
								disabled={index === 0}
								class="rounded-md bg-base-800 p-2 text-base-200 transition-colors hover:bg-base-700 disabled:cursor-not-allowed disabled:opacity-40"
								aria-label="Previous trade"
							>
								<Icon name="skip-back" />
							</button>
							<button
								type="button"
								onclick={() => (playing = !playing)}
								class="flex items-center gap-1.5 rounded-md bg-accent-strong px-3 py-2 text-xs font-semibold text-base-950 transition-colors hover:bg-accent"
							>
								<Icon name={playing ? 'pause' : 'play'} />
								{playing ? 'Pause' : 'Play'}
							</button>
							<button
								type="button"
								onclick={next}
								disabled={index >= total - 1}
								class="rounded-md bg-base-800 p-2 text-base-200 transition-colors hover:bg-base-700 disabled:cursor-not-allowed disabled:opacity-40"
								aria-label="Next trade"
							>
								<Icon name="skip-forward" />
							</button>
						</div>

						<label class="flex min-w-48 flex-1 items-center gap-3">
							<input
								type="range"
								min="0"
								max={Math.max(total - 1, 0)}
								step="1"
								value={index}
								oninput={(event) => {
									playing = false;
									step = Number(event.currentTarget.value);
								}}
								class="w-full accent-accent"
								aria-label="Replay position"
							/>
							<span class="font-mono text-xs whitespace-nowrap text-base-300">
								{index + 1} / {total}
							</span>
						</label>
					</section>

					<!-- Running totals -->
					<div class="grid grid-cols-3 gap-3">
						<div class="rounded-lg border border-base-700 bg-base-850 p-3">
							<div class="text-[11px] tracking-wide text-base-500 uppercase">Cumulative P&L</div>
							<div
								class="mt-1 font-mono text-lg font-semibold"
								class:text-long={cumulativePnl > 0}
								class:text-short={cumulativePnl < 0}
								class:text-base-50={cumulativePnl === 0}
							>
								{fmtSigned(cumulativePnl)}
							</div>
						</div>
						<div class="rounded-lg border border-base-700 bg-base-850 p-3">
							<div class="text-[11px] tracking-wide text-base-500 uppercase">Win rate so far</div>
							<div class="mt-1 font-mono text-lg font-semibold text-base-50">
								{(winRate * 100).toFixed(1)}%
							</div>
						</div>
						<div class="rounded-lg border border-base-700 bg-base-850 p-3">
							<div class="text-[11px] tracking-wide text-base-500 uppercase">Step</div>
							<div class="mt-1 font-mono text-lg font-semibold text-base-50">
								{index + 1} <span class="text-base-500">/ {total}</span>
							</div>
						</div>
					</div>

					<!-- Current trade card -->
					<section class="rounded-lg border border-base-700 bg-base-850 p-4">
						<header class="flex items-center justify-between gap-2">
							<div class="flex items-center gap-2">
								<span
									class="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-bold {sideMeta(
										trade.side
									).tone} {sideMeta(trade.side).bg}"
								>
									<Icon name={sideMeta(trade.side).icon} />
									{trade.side}
								</span>
								<span class="font-mono text-sm font-semibold text-base-100">{trade.symbol}</span>
							</div>
							<span class="rounded bg-base-800 px-1.5 py-0.5 text-[11px] text-base-300">
								{trade.exit_reason}
							</span>
						</header>

						<div class="mt-3 grid gap-2 sm:grid-cols-2">
							<div class="rounded bg-base-900 px-3 py-2">
								<div class="text-[10px] text-base-500 uppercase">Entry</div>
								<div class="font-mono text-sm text-base-100">{fmtPrice(trade.entry_price)}</div>
								<div class="font-mono text-[11px] text-base-500">{fmtTs(trade.entry_ts)}</div>
							</div>
							<div class="rounded bg-base-900 px-3 py-2">
								<div class="text-[10px] text-base-500 uppercase">Exit</div>
								<div class="font-mono text-sm text-base-100">{fmtPrice(trade.exit_price)}</div>
								<div class="font-mono text-[11px] text-base-500">{fmtTs(trade.exit_ts)}</div>
							</div>
						</div>

						<div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
							<div class="rounded bg-base-900 px-3 py-2">
								<div class="text-[10px] text-base-500 uppercase">P&L</div>
								<div
									class="font-mono text-sm"
									class:text-long={trade.pnl > 0}
									class:text-short={trade.pnl < 0}
									class:text-base-100={trade.pnl === 0}
								>
									{fmtSigned(trade.pnl)}
								</div>
							</div>
							<div class="rounded bg-base-900 px-3 py-2">
								<div class="text-[10px] text-base-500 uppercase">Return</div>
								<div
									class="font-mono text-sm"
									class:text-long={trade.return_pct > 0}
									class:text-short={trade.return_pct < 0}
									class:text-base-100={trade.return_pct === 0}
								>
									{fmtPct(trade.return_pct)}
								</div>
							</div>
							<div class="rounded bg-base-900 px-3 py-2">
								<div class="text-[10px] text-base-500 uppercase">MFE</div>
								<div class="font-mono text-sm text-long">{fmtPrice(trade.mfe)}</div>
							</div>
							<div class="rounded bg-base-900 px-3 py-2">
								<div class="text-[10px] text-base-500 uppercase">MAE</div>
								<div class="font-mono text-sm text-short">{fmtPrice(trade.mae)}</div>
							</div>
						</div>
					</section>

					<!-- Equity curve up to the current trade's exit -->
					<EquityCurveChart points={visibleCurve} title="Equity through trade {index + 1}" />
				</div>
			{/if}
		</div>
	</div>
</div>
