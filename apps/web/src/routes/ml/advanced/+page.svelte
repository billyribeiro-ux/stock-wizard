<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import FeatureImportanceChart from '$lib/components/FeatureImportanceChart.svelte';
	import {
		listScanners,
		getFeatureInfo,
		getLeakageAudit,
		calibrateModel,
		trainMeta,
		mineRules,
		getAdvancedJob
	} from './data.remote';
	import type { FeatureInfoReport, LeakageAuditReport, MlAdvancedJob } from '$lib/types';

	const TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d', '1w'] as const;
	const HISTORY_WINDOWS = ['1y', '2y', '5y', '10y'] as const;

	// --- Shared form state ----------------------------------------------------
	let symbol = $state('SPY');
	let timeframe = $state('1d');
	let history = $state('2y');
	let horizon = $state(10);
	let scannerId = $state('');

	// --- Feature info ---------------------------------------------------------
	let featureArgs = $state<{
		symbol: string;
		timeframe: string;
		history: string;
		horizon: number;
	} | null>(null);
	let featureError = $state<string | null>(null);

	// --- Leakage audit --------------------------------------------------------
	let leakageArgs = $state<{ symbol: string; timeframe: string; history: string } | null>(null);
	let leakageError = $state<string | null>(null);

	// --- Self-learning jobs (calibrate / meta / mine) -------------------------
	type JobKind = 'calibrate' | 'meta' | 'mine';
	let jobId = $state<string | null>(null);
	let jobKind = $state<JobKind | null>(null);
	let jobSubmitting = $state(false);
	let jobError = $state<string | null>(null);

	function isTraining(status: string | undefined): boolean {
		return status?.toLowerCase() === 'training';
	}

	// Poll the active self-learning job until it leaves the `training` state.
	$effect(() => {
		const id = jobId;
		if (!id) return;
		const status = getAdvancedJob(id).current?.status;
		if (status && !isTraining(status)) return;
		const handle = setInterval(() => {
			getAdvancedJob(id).refresh();
		}, 1500);
		return () => clearInterval(handle);
	});

	function trimmedSymbol(): string {
		return symbol.trim().toUpperCase();
	}

	function runFeatureInfo(): void {
		featureError = null;
		if (!trimmedSymbol()) {
			featureError = 'Enter a symbol.';
			return;
		}
		featureArgs = { symbol: trimmedSymbol(), timeframe, history, horizon };
	}

	function runLeakageAudit(): void {
		leakageError = null;
		if (!trimmedSymbol()) {
			leakageError = 'Enter a symbol.';
			return;
		}
		leakageArgs = { symbol: trimmedSymbol(), timeframe, history };
	}

	async function runJob(kind: JobKind): Promise<void> {
		jobError = null;
		if (!trimmedSymbol()) {
			jobError = 'Enter a symbol.';
			return;
		}
		if ((kind === 'calibrate' || kind === 'meta') && !scannerId) {
			jobError = 'Pick a scanner.';
			return;
		}

		jobSubmitting = true;
		jobKind = kind;
		try {
			let model_id: string;
			if (kind === 'calibrate') {
				({ model_id } = await calibrateModel({
					scanner_id: scannerId,
					symbol: trimmedSymbol(),
					timeframe,
					history,
					horizon
				}));
			} else if (kind === 'meta') {
				({ model_id } = await trainMeta({
					scanner_id: scannerId,
					symbol: trimmedSymbol(),
					timeframe,
					history,
					horizon
				}));
			} else {
				({ model_id } = await mineRules({
					symbol: trimmedSymbol(),
					timeframe,
					history,
					horizon
				}));
			}
			jobId = model_id;
		} catch (error) {
			jobError = error instanceof Error ? error.message : 'Failed to start job.';
			jobKind = null;
		} finally {
			jobSubmitting = false;
		}
	}

	function fmtPct(value: number | undefined): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return `${(value * 100).toFixed(1)}%`;
	}

	function fmtNum(value: number | undefined): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return value.toFixed(3);
	}

	/** Build a feature → mutual-information map for the MI bar chart. */
	function miMap(report: FeatureInfoReport): Record<string, number> {
		const out: Record<string, number> = {};
		for (const r of report.rankings) out[r.feature] = r.mutual_information;
		return out;
	}
</script>

<svelte:head>
	<title>Self-Learning · ML Lab · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="brain" class="text-accent" />
			ML Lab
			<span class="text-base-600">/</span>
			<span class="flex items-center gap-1.5 text-base-200">
				<Icon name="function" class="text-accent" />
				Self-Learning
			</span>
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Probe feature information, audit for lookahead, and run self-learning jobs: probability
			calibration, meta-labeling and rule mining.
		</p>
		<nav class="mt-3 flex items-center gap-2 text-sm">
			<a
				href="/ml"
				class="rounded-md border border-base-700 bg-base-900 px-3 py-1.5 font-medium text-base-300 transition-colors hover:border-base-600 hover:text-base-100"
			>
				Train model
			</a>
			<span
				class="rounded-md border border-accent/40 bg-base-850 px-3 py-1.5 font-medium text-accent"
			>
				Self-Learning
			</span>
		</nav>
	</header>

	<!-- Shared configuration -->
	<section class="mb-6 rounded-lg border border-base-700 bg-base-850 p-5">
		<h2 class="mb-3 text-xs font-medium tracking-wide text-base-400 uppercase">Configuration</h2>
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
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
			<label class="block">
				<span class="mb-1 block text-xs font-medium text-base-300">Horizon</span>
				<input
					type="number"
					step="1"
					min="1"
					bind:value={horizon}
					class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
				/>
			</label>
			<label class="block">
				<span class="mb-1 block text-xs font-medium text-base-300">Scanner</span>
				<svelte:boundary>
					{#snippet pending()}
						<div class="h-[38px] animate-pulse rounded-md bg-base-900"></div>
					{/snippet}
					{#await listScanners() then scanners}
						<select
							bind:value={scannerId}
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
						>
							<option value="">— pick —</option>
							{#each scanners as s (s.scanner_id)}
								<option value={s.scanner_id}>{s.name}</option>
							{/each}
						</select>
					{/await}
				</svelte:boundary>
			</label>
		</div>
		<p class="mt-2 text-[11px] text-base-500">
			Scanner is required for calibration and meta-labeling; rule mining ignores it.
		</p>
	</section>

	<div class="space-y-6">
		<!-- Feature information (mutual information) -->
		<section class="rounded-lg border border-base-700 bg-base-850 p-5">
			<div class="mb-4 flex items-center justify-between gap-3">
				<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
					<Icon name="function" class="text-accent" />
					Feature information
					<span class="text-xs font-normal text-base-500">mutual information vs. forward label</span
					>
				</h2>
				<button
					type="button"
					onclick={runFeatureInfo}
					class="flex items-center gap-1.5 rounded-md bg-accent-strong px-3 py-1.5 text-xs font-semibold text-base-950 transition-colors hover:bg-accent"
				>
					<Icon name="play" />
					Analyze features
				</button>
			</div>

			{#if featureError}
				<p class="flex items-center gap-1.5 text-sm text-danger">
					<Icon name="warning-circle" />
					{featureError}
				</p>
			{/if}

			{#if !featureArgs}
				<p class="text-xs text-base-500">
					Run an analysis to rank features by information content.
				</p>
			{:else}
				<svelte:boundary>
					{#snippet pending()}
						<div class="h-80 animate-pulse rounded-md bg-base-900"></div>
					{/snippet}
					{#await getFeatureInfo(featureArgs) then report}
						<div class="grid gap-3 sm:grid-cols-3">
							<div class="rounded-lg border border-base-700 bg-base-900 p-3">
								<div class="text-[11px] tracking-wide text-base-500 uppercase">Label entropy</div>
								<div class="mt-1 font-mono text-lg font-semibold text-base-50">
									{fmtNum(report.label_entropy)}
								</div>
							</div>
							<div class="rounded-lg border border-base-700 bg-base-900 p-3">
								<div class="text-[11px] tracking-wide text-base-500 uppercase">Base rate</div>
								<div class="mt-1 font-mono text-lg font-semibold text-base-50">
									{fmtPct(report.base_rate)}
								</div>
							</div>
							<div class="rounded-lg border border-base-700 bg-base-900 p-3">
								<div class="text-[11px] tracking-wide text-base-500 uppercase">Samples</div>
								<div class="mt-1 font-mono text-lg font-semibold text-base-50">
									{report.n_samples.toLocaleString()}
								</div>
							</div>
						</div>

						<div class="mt-4">
							<FeatureImportanceChart
								importance={miMap(report)}
								title="Mutual information by feature"
							/>
						</div>

						<div class="mt-4">
							<h3 class="mb-2 flex items-center gap-2 text-xs font-semibold text-base-200">
								<Icon name="link" class="text-accent" />
								Redundant feature pairs
							</h3>
							{#if report.redundant_pairs.length === 0}
								<p class="text-xs text-base-500">No highly-redundant pairs detected.</p>
							{:else}
								<ul class="flex flex-wrap gap-2">
									{#each report.redundant_pairs as pair, i (i)}
										<li
											class="flex items-center gap-2 rounded-md border border-base-700 bg-base-900 px-2.5 py-1 text-xs"
										>
											<span class="font-mono text-base-200">{pair[0]}</span>
											<Icon name="arrows-down-up" class="text-base-500" />
											<span class="font-mono text-base-200">{pair[1]}</span>
											<span class="font-mono text-warn">{fmtNum(pair[2])}</span>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/await}
				</svelte:boundary>
			{/if}
		</section>

		<!-- Leakage audit -->
		<section class="rounded-lg border border-base-700 bg-base-850 p-5">
			<div class="mb-4 flex items-center justify-between gap-3">
				<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
					<Icon name="shield-check" class="text-accent" />
					Leakage audit
					<span class="text-xs font-normal text-base-500">lookahead probe</span>
				</h2>
				<button
					type="button"
					onclick={runLeakageAudit}
					class="flex items-center gap-1.5 rounded-md bg-accent-strong px-3 py-1.5 text-xs font-semibold text-base-950 transition-colors hover:bg-accent"
				>
					<Icon name="play" />
					Run audit
				</button>
			</div>

			{#if leakageError}
				<p class="flex items-center gap-1.5 text-sm text-danger">
					<Icon name="warning-circle" />
					{leakageError}
				</p>
			{/if}

			{#if !leakageArgs}
				<p class="text-xs text-base-500">Run an audit to probe features for lookahead leakage.</p>
			{:else}
				<svelte:boundary>
					{#snippet pending()}
						<div class="h-24 animate-pulse rounded-md bg-base-900"></div>
					{/snippet}
					{#await getLeakageAudit(leakageArgs) then report}
						{@render leakagePanel(report)}
					{/await}
				</svelte:boundary>
			{/if}
		</section>

		<!-- Self-learning jobs -->
		<section class="rounded-lg border border-base-700 bg-base-850 p-5">
			<h2 class="mb-1 flex items-center gap-2 text-sm font-semibold text-base-100">
				<Icon name="scales" class="text-accent" />
				Self-learning jobs
			</h2>
			<p class="mb-4 text-xs text-base-500">
				Each job trains on historical data and polls until complete.
			</p>

			<div class="flex flex-wrap gap-2">
				<button
					type="button"
					onclick={() => runJob('calibrate')}
					disabled={jobSubmitting}
					class="flex items-center gap-1.5 rounded-md border border-base-700 bg-base-900 px-3 py-1.5 text-xs font-semibold text-base-100 transition-colors hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
				>
					<Icon name="scales" />
					Calibrate
				</button>
				<button
					type="button"
					onclick={() => runJob('meta')}
					disabled={jobSubmitting}
					class="flex items-center gap-1.5 rounded-md border border-base-700 bg-base-900 px-3 py-1.5 text-xs font-semibold text-base-100 transition-colors hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
				>
					<Icon name="brain" />
					Meta-label
				</button>
				<button
					type="button"
					onclick={() => runJob('mine')}
					disabled={jobSubmitting}
					class="flex items-center gap-1.5 rounded-md border border-base-700 bg-base-900 px-3 py-1.5 text-xs font-semibold text-base-100 transition-colors hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
				>
					<Icon name="magnifying-glass" />
					Mine rules
				</button>
			</div>

			{#if jobError}
				<p class="mt-3 flex items-center gap-1.5 text-sm text-danger">
					<Icon name="warning-circle" />
					{jobError}
				</p>
			{/if}

			{#if jobId}
				<div class="mt-4">
					<svelte:boundary>
						{#snippet pending()}
							<div class="h-40 animate-pulse rounded-md bg-base-900"></div>
						{/snippet}
						{@render jobPanel(await getAdvancedJob(jobId))}
						{#snippet failed(error, reset)}
							<div class="rounded-lg border border-danger/40 bg-base-900 p-4 text-center">
								<Icon name="warning-circle" class="text-2xl text-danger" />
								<p class="mt-2 text-sm text-base-200">
									{error instanceof Error ? error.message : 'Failed to load job.'}
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
				</div>
			{/if}
		</section>
	</div>
</div>

{#snippet leakagePanel(report: LeakageAuditReport)}
	{#if report.clean}
		<div
			class="flex items-center gap-2 rounded-md border border-ok/40 bg-long-soft px-4 py-3 text-sm font-medium text-ok"
		>
			<Icon name="shield-check" class="text-lg" />
			✓ no lookahead detected
		</div>
	{:else}
		<div
			class="flex items-center gap-2 rounded-md border border-danger/40 bg-short-soft px-4 py-3 text-sm font-medium text-danger"
		>
			<Icon name="warning-circle" class="text-lg" />
			lookahead leakage detected
		</div>
	{/if}
	<p class="mt-3 text-sm text-base-300">{report.summary}</p>
	<div class="mt-3 flex flex-wrap gap-4 text-xs text-base-500">
		<span>probes <span class="font-mono text-base-300">{report.n_probes}</span></span>
		<span>features <span class="font-mono text-base-300">{report.features_checked}</span></span>
		<span>max |Δ| <span class="font-mono text-base-300">{fmtNum(report.max_abs_diff)}</span></span>
	</div>
	{#if report.leaks.length > 0}
		<ul class="mt-3 space-y-1.5">
			{#each report.leaks as leak, i (i)}
				<li
					class="flex items-center justify-between gap-3 rounded-md border border-base-700 bg-base-900 px-3 py-1.5 text-xs"
				>
					<span class="font-mono text-danger">{leak.feature}</span>
					{#if leak.detail}
						<span class="truncate text-base-400">{leak.detail}</span>
					{/if}
					{#if leak.abs_diff !== undefined}
						<span class="font-mono text-warn">{fmtNum(leak.abs_diff)}</span>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
{/snippet}

{#snippet jobPanel(job: MlAdvancedJob)}
	{#if isTraining(job.status)}
		<div
			class="flex h-40 flex-col items-center justify-center gap-3 rounded-lg border border-base-700 bg-base-900 text-base-300"
		>
			<Icon name="spinner-gap" class="animate-spin text-3xl text-accent" />
			<p class="text-sm">Running {jobKind ?? 'job'}…</p>
			<p class="font-mono text-xs text-base-500">{job.model_id}</p>
		</div>
	{:else if job.status.toLowerCase() === 'error'}
		<div class="rounded-lg border border-danger/40 bg-base-900 p-4 text-center">
			<Icon name="warning-circle" class="text-2xl text-danger" />
			<p class="mt-2 text-sm text-base-200">Job failed.</p>
		</div>
	{:else}
		{@const report = job.report}
		<div class="rounded-lg border border-base-700 bg-base-900 p-4">
			<div class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
				<Icon name="check-circle" class="text-ok" />
				{job.name}
				<span class="font-mono text-xs text-base-500">v{job.version}</span>
			</div>

			{#if report?.calibrator}
				{@const cal = report.calibrator}
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Samples</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{cal.n_samples.toLocaleString()}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Base rate</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{fmtPct(cal.base_rate)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Brier raw</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{fmtNum(cal.brier_raw)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Brier calibrated</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{fmtNum(cal.brier_calibrated)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Improved</div>
						<div
							class="mt-1 font-mono text-base font-semibold"
							class:text-ok={cal.improved}
							class:text-danger={!cal.improved}
						>
							{cal.improved ? 'yes' : 'no'}
						</div>
					</div>
				</div>
			{:else if report?.meta}
				{@const meta = report.meta}
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Primary win rate</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{fmtPct(meta.primary_win_rate)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Meta CV AUC</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{fmtNum(meta.meta_cv_auc)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Precision @ thr</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{fmtPct(meta.meta_precision_at_threshold)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Take fraction</div>
						<div class="mt-1 font-mono text-base font-semibold text-base-50">
							{fmtPct(meta.take_fraction)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Lift vs primary</div>
						<div
							class="mt-1 font-mono text-base font-semibold"
							class:text-long={meta.lift_vs_primary > 0}
							class:text-short={meta.lift_vs_primary < 0}
						>
							{fmtNum(meta.lift_vs_primary)}
						</div>
					</div>
					<div class="rounded-md border border-base-700 bg-base-850 p-3">
						<div class="text-[11px] tracking-wide text-base-500 uppercase">Fitted</div>
						<div
							class="mt-1 font-mono text-base font-semibold"
							class:text-ok={meta.fitted}
							class:text-danger={!meta.fitted}
						>
							{meta.fitted ? 'yes' : 'no'}
						</div>
					</div>
				</div>
			{:else if report?.mined_rules}
				{#if report.mined_rules.length === 0}
					<p class="text-xs text-base-500">No rules mined.</p>
				{:else}
					<div class="overflow-x-auto">
						<table class="w-full text-xs">
							<thead>
								<tr class="text-left text-base-500">
									<th class="py-1.5 pr-3 font-medium">Rule</th>
									<th class="py-1.5 pr-3 text-right font-medium">Train hits</th>
									<th class="py-1.5 pr-3 text-right font-medium">Train mean ret</th>
									<th class="py-1.5 pr-3 text-right font-medium">Valid mean ret</th>
									<th class="py-1.5 text-right font-medium">Holds up</th>
								</tr>
							</thead>
							<tbody>
								{#each report.mined_rules as rule, i (i)}
									<tr class="border-t border-base-800">
										<td class="py-1.5 pr-3 font-mono text-base-200">{rule.description}</td>
										<td class="py-1.5 pr-3 text-right font-mono text-base-300">{rule.train_hits}</td
										>
										<td
											class="py-1.5 pr-3 text-right font-mono"
											class:text-long={rule.train_mean_return > 0}
											class:text-short={rule.train_mean_return < 0}
										>
											{fmtPct(rule.train_mean_return)}
										</td>
										<td
											class="py-1.5 pr-3 text-right font-mono"
											class:text-long={rule.valid_mean_return > 0}
											class:text-short={rule.valid_mean_return < 0}
										>
											{fmtPct(rule.valid_mean_return)}
										</td>
										<td class="py-1.5 text-right">
											{#if rule.holds_up}
												<span
													class="inline-flex items-center gap-1 rounded-full bg-long-soft px-1.5 py-0.5 text-[10px] font-semibold text-long"
												>
													<Icon name="check" />
													holds up
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
			{:else}
				<p class="text-xs text-base-500">Job finished but returned no report.</p>
			{/if}
		</div>
	{/if}
{/snippet}
