<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { runDiscovery, getDiscovery, listDiscoveries, promoteRule } from './data.remote';
	import type {
		Discovery,
		DiscoveryEvent,
		DiscoveryReasonStat,
		DiscoveryReport,
		SuggestedRule
	} from '$lib/types';

	const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '1d', '1wk'] as const;
	const LOOKBACKS = ['5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', '20y', '30y'] as const;

	/** Trade-style presets: each one pins a timeframe and a sensible lookback. */
	const PRESETS = [
		{ label: 'Scalping', timeframe: '5m', lookback: '1mo' },
		{ label: 'Intraday', timeframe: '15m', lookback: '1mo' },
		{ label: 'Day trading', timeframe: '1h', lookback: '1mo' },
		{ label: 'Swing', timeframe: '1d', lookback: '1y' }
	] as const;

	// --- Form state ----------------------------------------------------------
	let symbol = $state('SPY');
	let timeframe = $state('1d');
	let history = $state('1y');
	let minMoveAtr = $state(1.5);

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	// Currently-loaded discovery id (drives the result panel + polling).
	let activeId = $state<string | null>(null);

	const activePreset = $derived(PRESETS.find((p) => p.timeframe === timeframe)?.label ?? null);

	function applyPreset(preset: (typeof PRESETS)[number]): void {
		timeframe = preset.timeframe;
		history = preset.lookback;
	}

	function isTerminal(status: string | undefined): boolean {
		const s = status?.toLowerCase();
		return s === 'done' || s === 'error';
	}

	// Poll the active discovery until it reaches a terminal state. We read the
	// query's `current` value so the effect re-runs as the status changes and
	// stops polling once the run is done/errored.
	$effect(() => {
		const id = activeId;
		if (!id) return;
		const status = getDiscovery(id).current?.status;
		if (isTerminal(status)) return;
		const handle = setInterval(() => {
			getDiscovery(id).refresh();
		}, 1500);
		return () => clearInterval(handle);
	});

	async function submit(): Promise<void> {
		errorMessage = null;
		if (!symbol.trim()) {
			errorMessage = 'Enter a symbol.';
			return;
		}

		submitting = true;
		try {
			const { discovery_id } = await runDiscovery({
				symbol: symbol.trim().toUpperCase(),
				timeframe,
				history,
				min_move_atr: minMoveAtr
			});
			activeId = discovery_id;
			await listDiscoveries().refresh();
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start discovery.';
		} finally {
			submitting = false;
		}
	}

	function loadPast(id: string): void {
		errorMessage = null;
		activeId = id;
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

	/** Latest ~50 turning points, newest first. */
	function latestEvents(report: DiscoveryReport): DiscoveryEvent[] {
		return [...report.events]
			.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
			.slice(0, 50);
	}

	function reasonTooltip(event: DiscoveryEvent): string {
		return event.reasons.map((r) => `${r.label}: ${r.detail}`).join('\n');
	}

	function reasonLabels(event: DiscoveryEvent): string {
		return event.reasons.map((r) => r.label).join(', ');
	}

	/** Format a lift value as a signed multiplier / delta with two decimals. */
	function fmtLift(value: number): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
	}

	function fmtNum(value: number): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return value.toFixed(2);
	}

	/** Render a rule condition as a compact predicate, e.g. "rsi14 < 35". */
	function conditionText(rule: SuggestedRule): string {
		return rule.conditions.map((c) => `${c.feature} ${c.op} ${c.threshold}`).join(' and ');
	}

	// --- Promote-to-scan state -----------------------------------------------
	// Keyed by rule name so each row tracks its own pending / result / error.
	let promoting = $state<Record<string, boolean>>({});
	let promotedRun = $state<Record<string, string>>({});
	let promoteError = $state<Record<string, string>>({});

	async function promote(report: DiscoveryReport, rule: SuggestedRule): Promise<void> {
		promoting = { ...promoting, [rule.name]: true };
		promoteError = { ...promoteError, [rule.name]: '' };
		try {
			const { run_id } = await promoteRule({
				symbol: report.symbol,
				timeframe: report.timeframe,
				direction: rule.direction,
				name: rule.name,
				conditions: rule.conditions
			});
			promotedRun = { ...promotedRun, [rule.name]: run_id };
		} catch (error) {
			promoteError = {
				...promoteError,
				[rule.name]: error instanceof Error ? error.message : 'Failed to promote rule.'
			};
		} finally {
			promoting = { ...promoting, [rule.name]: false };
		}
	}
</script>

<svelte:head>
	<title>Discovery Lab · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="detective" class="text-accent" />
			Discovery Lab
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Replay past price history and self-identify why price was bought and sold at every significant
			turn, per trade style.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[20rem_1fr]">
		<!-- Config + past runs column -->
		<div class="space-y-6">
			<!-- Config form -->
			<section class="space-y-4 rounded-lg border border-base-700 bg-base-850 p-5">
				<h2 class="text-xs font-medium tracking-wide text-base-400 uppercase">Configuration</h2>

				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">Symbol</span>
					<input
						type="text"
						bind:value={symbol}
						placeholder="SPY"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
				</label>

				<div>
					<span class="mb-1 block text-xs font-medium text-base-300">Trade style</span>
					<div class="grid grid-cols-2 gap-2">
						{#each PRESETS as preset (preset.label)}
							<button
								type="button"
								onclick={() => applyPreset(preset)}
								class="rounded-md border px-2 py-1.5 text-xs font-medium transition-colors"
								class:border-accent={activePreset === preset.label}
								class:bg-base-800={activePreset === preset.label}
								class:text-base-100={activePreset === preset.label}
								class:border-base-700={activePreset !== preset.label}
								class:text-base-400={activePreset !== preset.label}
								class:hover:border-base-600={activePreset !== preset.label}
								class:hover:text-base-200={activePreset !== preset.label}
							>
								{preset.label}
								<span class="ml-1 font-mono text-[10px] text-base-500">{preset.timeframe}</span>
							</button>
						{/each}
					</div>
				</div>

				<div class="grid grid-cols-2 gap-3">
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
					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">Look-back</span>
						<select
							bind:value={history}
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
						>
							{#each LOOKBACKS as lb (lb)}
								<option value={lb}>{lb}</option>
							{/each}
						</select>
					</label>
				</div>

				<p class="flex items-start gap-1.5 text-[11px] leading-snug text-base-500">
					<Icon name="info" class="mt-0.5" />
					Intraday timeframes are limited by the data source: 1m ≈ 7d max, 5m–1h ≈ 60d max.
				</p>

				<label class="block border-t border-base-800 pt-4">
					<span class="mb-1 flex items-center justify-between text-xs font-medium text-base-300">
						<span class="flex items-center gap-1.5">
							<Icon name="sliders-horizontal" />
							Minimum significant move
						</span>
						<span class="font-mono text-base-100">{minMoveAtr.toFixed(1)}× ATR</span>
					</span>
					<input
						type="range"
						min="0.5"
						max="5"
						step="0.1"
						bind:value={minMoveAtr}
						class="w-full accent-accent"
					/>
				</label>

				{#if errorMessage}
					<p class="flex items-center gap-1.5 text-sm text-danger">
						<Icon name="warning-circle" />
						{errorMessage}
					</p>
				{/if}

				<button
					type="button"
					onclick={submit}
					disabled={submitting}
					class="flex w-full items-center justify-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
				>
					{#if submitting}
						<Icon name="spinner-gap" class="animate-spin" />
						Enqueuing…
					{:else}
						<Icon name="play" />
						Run Discovery
					{/if}
				</button>
			</section>

			<!-- Past discoveries -->
			<section class="rounded-lg border border-base-700 bg-base-850 p-4">
				<header class="mb-3 flex items-center justify-between">
					<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
						<Icon name="clock-counter-clockwise" class="text-accent" />
						Past discoveries
					</h2>
					<button
						type="button"
						onclick={() => listDiscoveries().refresh()}
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

					{#await listDiscoveries() then { items }}
						{#if items.length === 0}
							<p class="text-xs text-base-500">No discoveries yet.</p>
						{:else}
							<ul class="space-y-2">
								{#each items as item (item.discovery_id)}
									<li>
										<button
											type="button"
											onclick={() => loadPast(item.discovery_id)}
											class="w-full rounded-md border p-2.5 text-left transition-colors"
											class:border-accent={activeId === item.discovery_id}
											class:border-base-700={activeId !== item.discovery_id}
											class:hover:border-base-600={activeId !== item.discovery_id}
										>
											<div class="flex items-center justify-between gap-2">
												<span class="truncate font-mono text-xs font-medium text-base-100">
													{item.symbol}
												</span>
												<span class="text-[11px] font-medium {statusTone(item.status)}">
													{item.status}
												</span>
											</div>
											<div class="mt-1 flex items-center gap-3 text-[11px] text-base-500">
												<span>{item.timeframe}</span>
												<span>{fmtTs(item.created_at)}</span>
											</div>
											{#if item.metrics}
												<div
													class="mt-1 flex items-center gap-3 font-mono text-[11px] text-base-400"
												>
													{#if item.metrics.n_events !== undefined}
														<span>turns {item.metrics.n_events}</span>
													{/if}
													{#if item.metrics.n_bars !== undefined}
														<span>bars {item.metrics.n_bars}</span>
													{/if}
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
					<Icon name="detective" class="text-3xl" />
					<p>Run a discovery or pick a past run to inspect what the engine learned.</p>
				</div>
			{:else}
				{#snippet reasonTable(
					title: string,
					tone: 'long' | 'short',
					rows: DiscoveryReasonStat[],
					baseline: number
				)}
					<section class="min-w-0 rounded-lg border border-base-700 bg-base-850 p-4">
						<div class="mb-3 flex items-center justify-between gap-2">
							<h3
								class="flex items-center gap-2 text-sm font-semibold {tone === 'long'
									? 'text-long'
									: 'text-short'}"
							>
								<Icon name={tone === 'long' ? 'trend-up' : 'trend-down'} />
								{title}
							</h3>
							<span class="font-mono text-[11px] text-base-500">
								baseline {fmtPct(baseline)}
							</span>
						</div>
						{#if rows.length === 0}
							<p class="text-xs text-base-500">No reasons identified.</p>
						{:else}
							<div class="overflow-x-auto">
								<table class="w-full text-xs">
									<thead>
										<tr class="text-left text-base-500">
											<th class="py-1.5 pr-3 font-medium">Reason</th>
											<th class="py-1.5 pr-3 text-right font-medium">Count</th>
											<th class="py-1.5 pr-3 font-medium">% of events</th>
											<th class="py-1.5 pr-3 text-right font-medium">Avg fwd move</th>
											<th class="py-1.5 pr-3 text-right font-medium">Lift</th>
											<th class="py-1.5 pr-3 text-right font-medium">t-stat</th>
											<th class="py-1.5 pr-3 text-right font-medium">OOS lift</th>
											<th class="py-1.5 text-right font-medium">Validated</th>
										</tr>
									</thead>
									<tbody>
										{#each rows as row (row.code)}
											<tr class="border-t border-base-800">
												<td class="py-1.5 pr-3 text-base-200">{row.label}</td>
												<td class="py-1.5 pr-3 text-right font-mono text-base-300">{row.count}</td>
												<td class="py-1.5 pr-3">
													<div class="flex items-center gap-2">
														<div class="h-1.5 w-16 overflow-hidden rounded-full bg-base-800">
															<div
																class="h-full rounded-full {tone === 'long'
																	? 'bg-long'
																	: 'bg-short'}"
																style="width: {Math.min(
																	100,
																	Math.max(0, row.pct_of_events * 100)
																)}%"
															></div>
														</div>
														<span class="font-mono text-base-300">
															{(row.pct_of_events * 100).toFixed(0)}%
														</span>
													</div>
												</td>
												<td
													class="py-1.5 pr-3 text-right font-mono"
													class:text-long={row.avg_forward_move_pct > 0}
													class:text-short={row.avg_forward_move_pct < 0}
												>
													{fmtPct(row.avg_forward_move_pct)}
												</td>
												<td
													class="py-1.5 pr-3 text-right font-mono"
													class:text-long={row.lift > 0}
													class:text-short={row.lift < 0}
												>
													{fmtLift(row.lift)}
												</td>
												<td class="py-1.5 pr-3 text-right font-mono text-base-300">
													{fmtNum(row.t_stat)}
												</td>
												<td
													class="py-1.5 pr-3 text-right font-mono"
													class:text-long={row.oos_lift > 0}
													class:text-short={row.oos_lift < 0}
												>
													{fmtLift(row.oos_lift)}
												</td>
												<td class="py-1.5 text-right">
													{#if row.holds_up}
														<span
															class="inline-flex items-center gap-1 rounded-full bg-long-soft px-1.5 py-0.5 text-[10px] font-semibold text-long"
														>
															<Icon name="check" />
															validated
														</span>
													{:else}
														<span class="text-base-600">—</span>
													{/if}
												</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						{/if}
					</section>
				{/snippet}

				{#snippet resultPanel(disc: Discovery)}
					{#if !isTerminal(disc.status)}
						<div
							class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-base-700 bg-base-850 text-base-300"
						>
							<Icon name="spinner-gap" class="animate-spin text-3xl text-accent" />
							<p class="text-sm">
								Discovery <span class="font-medium {statusTone(disc.status)}">{disc.status}</span>…
							</p>
							<p class="font-mono text-xs text-base-500">{disc.discovery_id}</p>
						</div>
					{:else if disc.status.toLowerCase() === 'error'}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">{disc.error ?? 'Discovery failed.'}</p>
						</div>
					{:else if !disc.report}
						<div class="rounded-lg border border-base-700 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-warn" />
							<p class="mt-2 text-sm text-base-200">Discovery finished but returned no report.</p>
						</div>
					{:else}
						{@const report = disc.report}
						{@const events = latestEvents(report)}
						<div class="space-y-6">
							<div
								class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-base-700 bg-base-850 px-4 py-3"
							>
								<div>
									<div class="flex items-center gap-2 text-sm font-semibold text-base-100">
										<Icon name="lightbulb" class="text-accent" />
										{report.symbol}
										<span
											class="rounded-full border border-accent/40 bg-base-900 px-2 py-0.5 text-[11px] font-medium text-accent capitalize"
										>
											{report.trade_style}
										</span>
									</div>
									<div class="mt-0.5 flex items-center gap-3 text-xs text-base-500">
										<span>{report.timeframe}</span>
										<span class="font-mono">
											{report.period_start} → {report.period_end}
										</span>
									</div>
								</div>
								<div class="flex items-center gap-3">
									<a
										href={`/discovery/${disc.discovery_id}/export?fmt=csv`}
										class="flex items-center gap-1.5 rounded-md border border-base-700 bg-base-900 px-3 py-1.5 text-xs font-medium text-base-200 transition-colors hover:border-base-600"
									>
										<Icon name="file-csv" />
										Download CSV
									</a>
									<a
										href={`/discovery/${disc.discovery_id}/export?fmt=pdf`}
										class="flex items-center gap-1.5 rounded-md border border-base-700 bg-base-900 px-3 py-1.5 text-xs font-medium text-base-200 transition-colors hover:border-base-600"
									>
										<Icon name="file-pdf" />
										Download PDF
									</a>
									<span
										class="flex items-center gap-1.5 text-sm font-medium {statusTone(disc.status)}"
									>
										<Icon name="circle" />
										{disc.status}
									</span>
								</div>
							</div>

							<!-- Stat cards -->
							<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
								<div class="rounded-lg border border-base-700 bg-base-850 p-3">
									<div class="text-[11px] tracking-wide text-base-500 uppercase">
										Turning points
									</div>
									<div class="mt-1 font-mono text-lg font-semibold text-base-50">
										{report.n_events.toLocaleString()}
									</div>
								</div>
								<div class="rounded-lg border border-base-700 bg-base-850 p-3">
									<div class="text-[11px] tracking-wide text-base-500 uppercase">Bought</div>
									<div class="mt-1 font-mono text-lg font-semibold text-long">
										{report.n_bought.toLocaleString()}
									</div>
								</div>
								<div class="rounded-lg border border-base-700 bg-base-850 p-3">
									<div class="text-[11px] tracking-wide text-base-500 uppercase">Sold</div>
									<div class="mt-1 font-mono text-lg font-semibold text-short">
										{report.n_sold.toLocaleString()}
									</div>
								</div>
								<div class="rounded-lg border border-base-700 bg-base-850 p-3">
									<div class="text-[11px] tracking-wide text-base-500 uppercase">Bars analyzed</div>
									<div class="mt-1 font-mono text-lg font-semibold text-base-50">
										{report.n_bars.toLocaleString()}
									</div>
								</div>
							</div>

							<!-- Reason tables -->
							<div class="grid gap-6 xl:grid-cols-2">
								{@render reasonTable(
									'Why it was BOUGHT',
									'long',
									report.buy_reasons,
									report.baseline_buy_move
								)}
								{@render reasonTable(
									'Why it was SOLD',
									'short',
									report.sell_reasons,
									report.baseline_sell_move
								)}
							</div>

							<!-- Promotable rules -->
							{#if report.suggested_rules && report.suggested_rules.length > 0}
								<section class="rounded-lg border border-base-700 bg-base-850 p-4">
									<h3 class="mb-1 flex items-center gap-2 text-sm font-semibold text-base-100">
										<Icon name="magnifying-glass-plus" class="text-accent" />
										Promotable rules
									</h3>
									<p class="mb-3 text-xs text-base-500">
										Validated edges distilled into concrete rules. Promote one to launch a live
										scan.
									</p>
									<ul class="space-y-3">
										{#each report.suggested_rules as rule (rule.name)}
											<li
												class="flex flex-wrap items-center justify-between gap-3 rounded-md border border-base-700 bg-base-900 p-3"
											>
												<div class="min-w-0">
													<div class="flex items-center gap-2">
														<span
															class="rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase {rule.direction ===
															'LONG'
																? 'bg-long-soft text-long'
																: 'bg-short-soft text-short'}"
														>
															{rule.direction}
														</span>
														<span class="truncate text-sm font-medium text-base-100"
															>{rule.name}</span
														>
													</div>
													<div class="mt-1 font-mono text-xs text-base-300">
														{conditionText(rule)}
													</div>
													<div class="mt-1 flex items-center gap-3 text-[11px] text-base-500">
														<span>
															in-sample lift
															<span
																class="font-mono"
																class:text-long={rule.in_sample_lift > 0}
																class:text-short={rule.in_sample_lift < 0}
															>
																{fmtLift(rule.in_sample_lift)}
															</span>
														</span>
														<span>
															OOS lift
															<span
																class="font-mono"
																class:text-long={rule.oos_lift > 0}
																class:text-short={rule.oos_lift < 0}
															>
																{fmtLift(rule.oos_lift)}
															</span>
														</span>
													</div>
												</div>
												<div class="flex flex-col items-end gap-1.5">
													{#if promotedRun[rule.name]}
														<a
															href={`/results?run=${promotedRun[rule.name]}`}
															class="flex items-center gap-1.5 rounded-md border border-ok/40 bg-base-850 px-3 py-1.5 text-xs font-medium text-ok transition-colors hover:border-ok"
														>
															<Icon name="check-circle" />
															view run {promotedRun[rule.name].slice(0, 8)}
														</a>
													{:else}
														<button
															type="button"
															onclick={() => promote(report, rule)}
															disabled={promoting[rule.name]}
															class="flex items-center gap-1.5 rounded-md bg-accent-strong px-3 py-1.5 text-xs font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
														>
															{#if promoting[rule.name]}
																<Icon name="spinner-gap" class="animate-spin" />
																Promoting…
															{:else}
																<Icon name="play" />
																Promote to scan
															{/if}
														</button>
													{/if}
													{#if promoteError[rule.name]}
														<span class="flex items-center gap-1 text-[11px] text-danger">
															<Icon name="warning-circle" />
															{promoteError[rule.name]}
														</span>
													{/if}
												</div>
											</li>
										{/each}
									</ul>
								</section>
							{/if}

							<!-- Events timeline -->
							<section class="rounded-lg border border-base-700 bg-base-850 p-4">
								<h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
									<Icon name="list-checks" class="text-accent" />
									Turning points
									<span class="text-xs font-normal text-base-500">
										(latest {events.length} of {report.n_events}, newest first)
									</span>
								</h3>
								{#if events.length === 0}
									<p class="text-xs text-base-500">No significant turning points were found.</p>
								{:else}
									<div class="overflow-x-auto">
										<table class="w-full text-xs">
											<thead>
												<tr class="text-left text-base-500">
													<th class="py-1.5 pr-3 font-medium">Time</th>
													<th class="py-1.5 pr-3 font-medium">Kind</th>
													<th class="py-1.5 pr-3 text-right font-medium">Price</th>
													<th class="py-1.5 pr-3 text-right font-medium">Forward move</th>
													<th class="py-1.5 font-medium">Reasons</th>
												</tr>
											</thead>
											<tbody>
												{#each events as event, i (event.ts + event.kind + i)}
													<tr class="border-t border-base-800">
														<td class="py-1.5 pr-3 font-mono whitespace-nowrap text-base-300">
															{fmtTs(event.ts)}
														</td>
														<td class="py-1.5 pr-3">
															<span
																class="rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase {event.kind ===
																'bought'
																	? 'bg-long-soft text-long'
																	: 'bg-short-soft text-short'}"
															>
																{event.kind}
															</span>
														</td>
														<td class="py-1.5 pr-3 text-right font-mono text-base-200">
															{fmtPrice(event.price)}
														</td>
														<td
															class="py-1.5 pr-3 text-right font-mono whitespace-nowrap"
															class:text-long={event.forward_move_pct > 0}
															class:text-short={event.forward_move_pct < 0}
														>
															{fmtPct(event.forward_move_pct)}
															<span class="text-base-500">
																({event.forward_move_atr.toFixed(1)}× ATR)
															</span>
														</td>
														<td class="py-1.5 text-base-400" title={reasonTooltip(event)}>
															{reasonLabels(event)}
														</td>
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
					{@render resultPanel(await getDiscovery(activeId))}
					{#snippet failed(error, reset)}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">
								{error instanceof Error ? error.message : 'Failed to load discovery.'}
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
