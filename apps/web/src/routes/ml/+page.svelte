<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import FeatureImportanceChart from '$lib/components/FeatureImportanceChart.svelte';
	import { trainModel, getModel, listModels } from './data.remote';
	import type { MlModel } from '$lib/types';

	const TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d', '1w'] as const;
	const HISTORY_WINDOWS = ['1y', '2y', '5y', '10y'] as const;

	// --- Form state ----------------------------------------------------------
	let symbol = $state('SPY');
	let timeframe = $state('1d');
	let history = $state('2y');
	let horizon = $state(10);

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	// Currently-loaded model id (drives the result panel + polling).
	let activeId = $state<string | null>(null);

	function isTraining(status: string | undefined): boolean {
		return status?.toLowerCase() === 'training';
	}

	// Poll the active model until it leaves the `training` state. Reading the
	// query's `current` value re-runs the effect as status changes and stops
	// polling once training finishes.
	$effect(() => {
		const id = activeId;
		if (!id) return;
		const status = getModel(id).current?.status;
		if (status && !isTraining(status)) return;
		const handle = setInterval(() => {
			getModel(id).refresh();
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
			const { model_id } = await trainModel({
				symbol: symbol.trim().toUpperCase(),
				timeframe,
				history,
				horizon
			});
			activeId = model_id;
			await listModels().refresh();
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start training.';
		} finally {
			submitting = false;
		}
	}

	function loadPast(id: string): void {
		errorMessage = null;
		activeId = id;
	}

	function statusMeta(status: string): { tone: string; label: string } {
		const s = status?.toLowerCase();
		if (s === 'reliable') return { tone: 'text-ok', label: 'RELIABLE' };
		if (s === 'experimental') return { tone: 'text-warn', label: 'EXPERIMENTAL' };
		if (s === 'error') return { tone: 'text-danger', label: 'ERROR' };
		return { tone: 'text-base-400', label: 'TRAINING' };
	}

	function fmtPct(value: number | undefined): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return `${(value * 100).toFixed(1)}%`;
	}

	function fmtNum(value: number | undefined): string {
		if (value === undefined || value === null || Number.isNaN(value)) return '—';
		return value.toFixed(3);
	}

	function fmtTs(ts: string): string {
		const d = new Date(ts);
		return Number.isNaN(d.getTime()) ? ts : d.toLocaleString();
	}
</script>

<svelte:head>
	<title>ML Lab · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-7xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="brain" class="text-accent" />
			ML Lab
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Train a forward-return classifier on historical data and inspect its reliability.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[20rem_1fr]">
		<!-- Config + past models column -->
		<div class="space-y-6">
			<!-- Config form -->
			<section class="space-y-4 rounded-lg border border-base-700 bg-base-850 p-5">
				<h2 class="text-xs font-medium tracking-wide text-base-400 uppercase">Configuration</h2>

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

				<div class="grid grid-cols-2 gap-3">
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
				</div>

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
						Train Model
					{/if}
				</button>
			</section>

			<!-- Past models -->
			<section class="rounded-lg border border-base-700 bg-base-850 p-4">
				<header class="mb-3 flex items-center justify-between">
					<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
						<Icon name="clock-counter-clockwise" class="text-accent" />
						Past models
					</h2>
					<button
						type="button"
						onclick={() => listModels().refresh()}
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

					{#await listModels() then { items }}
						{#if items.length === 0}
							<p class="text-xs text-base-500">No models yet.</p>
						{:else}
							<ul class="space-y-2">
								{#each items as item (item.model_id)}
									{@const meta = statusMeta(item.status)}
									<li>
										<button
											type="button"
											onclick={() => loadPast(item.model_id)}
											class="w-full rounded-md border p-2.5 text-left transition-colors"
											class:border-accent={activeId === item.model_id}
											class:border-base-700={activeId !== item.model_id}
											class:hover:border-base-600={activeId !== item.model_id}
										>
											<div class="flex items-center justify-between gap-2">
												<span class="truncate text-xs font-medium text-base-100">
													{item.name}
												</span>
												<span class="text-[11px] font-medium {meta.tone}">
													{meta.label}
												</span>
											</div>
											<div class="mt-1 flex items-center gap-3 text-[11px] text-base-500">
												<span>v{item.version}</span>
												<span>{fmtTs(item.created_at)}</span>
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
					<Icon name="brain" class="text-3xl" />
					<p>Train a model or pick a past model to inspect its reliability.</p>
				</div>
			{:else}
				{#snippet resultPanel(model: MlModel)}
					{@const meta = statusMeta(model.status)}
					{#if isTraining(model.status)}
						<div
							class="flex h-96 flex-col items-center justify-center gap-3 rounded-lg border border-base-700 bg-base-850 text-base-300"
						>
							<Icon name="spinner-gap" class="animate-spin text-3xl text-accent" />
							<p class="text-sm">Training model…</p>
							<p class="font-mono text-xs text-base-500">{model.model_id}</p>
						</div>
					{:else if model.status.toLowerCase() === 'error'}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">Model training failed.</p>
						</div>
					{:else}
						{@const report = model.report}
						<div class="space-y-6">
							<div
								class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-base-700 bg-base-850 px-4 py-3"
							>
								<div>
									<div class="flex items-center gap-2 text-sm font-semibold text-base-100">
										<Icon name="brain" class="text-accent" />
										{model.name}
									</div>
									<div class="mt-0.5 flex items-center gap-3 text-xs text-base-500">
										<span>v{model.version}</span>
										{#if report}
											<span>{report.symbol}</span>
											<span>{report.timeframe}</span>
											<span>horizon {report.horizon}</span>
											<span>n {report.n_samples.toLocaleString()}</span>
										{/if}
									</div>
								</div>
								<span
									class="flex items-center gap-2 rounded-full border border-base-700 bg-base-900 px-3 py-1 text-xs font-medium {meta.tone}"
								>
									<Icon name="circle" />
									{meta.label}
								</span>
							</div>

							{#if report}
								<!-- Metric stat cards -->
								<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
									<div class="rounded-lg border border-base-700 bg-base-850 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">
											Test Accuracy
										</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtPct(report.test_accuracy)}
										</div>
										<div class="mt-0.5 text-[11px] text-base-500">
											base rate {fmtPct(report.base_rate)}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-850 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">
											Train Accuracy
										</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtPct(report.train_accuracy)}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-850 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">AUC</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtNum(report.auc)}
										</div>
									</div>
									<div class="rounded-lg border border-base-700 bg-base-850 p-3">
										<div class="text-[11px] tracking-wide text-base-500 uppercase">Brier</div>
										<div class="mt-1 font-mono text-lg font-semibold text-base-50">
											{fmtNum(report.brier)}
										</div>
									</div>
								</div>

								<!-- Feature importance -->
								<FeatureImportanceChart importance={report.feature_importance} />

								<!-- Calibration table -->
								<section class="rounded-lg border border-base-700 bg-base-850 p-4">
									<h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
										<Icon name="scales" class="text-accent" />
										Calibration
										<span class="text-xs font-normal text-base-500">
											({report.calibration.length} buckets)
										</span>
									</h3>
									{#if report.calibration.length === 0}
										<p class="text-xs text-base-500">No calibration data available.</p>
									{:else}
										<div class="overflow-x-auto">
											<table class="w-full text-xs">
												<thead>
													<tr class="text-left text-base-500">
														<th class="py-1.5 pr-3 text-right font-medium">Predicted</th>
														<th class="py-1.5 pr-3 text-right font-medium">Actual</th>
														<th class="py-1.5 text-right font-medium">Gap</th>
													</tr>
												</thead>
												<tbody>
													{#each report.calibration as point, i (i)}
														{@const gap = point.actual - point.predicted}
														<tr class="border-t border-base-800">
															<td class="py-1.5 pr-3 text-right font-mono text-base-200">
																{fmtPct(point.predicted)}
															</td>
															<td class="py-1.5 pr-3 text-right font-mono text-base-200">
																{fmtPct(point.actual)}
															</td>
															<td
																class="py-1.5 text-right font-mono"
																class:text-long={gap > 0}
																class:text-short={gap < 0}
															>
																{gap >= 0 ? '+' : ''}{fmtPct(gap)}
															</td>
														</tr>
													{/each}
												</tbody>
											</table>
										</div>
									{/if}
								</section>
							{/if}
						</div>
					{/if}
				{/snippet}

				<svelte:boundary>
					{#snippet pending()}
						<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
					{/snippet}
					{@render resultPanel(await getModel(activeId))}
					{#snippet failed(error, reset)}
						<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center">
							<Icon name="warning-circle" class="text-2xl text-danger" />
							<p class="mt-2 text-sm text-base-200">
								{error instanceof Error ? error.message : 'Failed to load model.'}
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
