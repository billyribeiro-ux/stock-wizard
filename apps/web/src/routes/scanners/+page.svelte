<script lang="ts">
	import { goto } from '$app/navigation';
	import Icon from '$lib/components/Icon.svelte';
	import { listScanners, runScan } from './data.remote';
	import {
		builder,
		parseSymbols,
		selectScanner,
		setParam,
		TIMEFRAMES,
		HISTORY_WINDOWS
	} from '$lib/state/scanner.svelte';
	import type { Scanner, JsonSchemaProperty } from '$lib/types';

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);

	/** Active category filter; '' means "all categories". */
	let categoryFilter = $state('');
	/** Free-text filter across name + description. */
	let searchQuery = $state('');

	const symbols = $derived(parseSymbols(builder.symbolsInput));

	const CATEGORY_LABELS: Record<string, string> = {
		structure: 'Structure',
		volume: 'Volume',
		options_gamma: 'Options / Gamma',
		volatility: 'Volatility',
		catalyst: 'Catalyst',
		ml: 'Machine Learning'
	};

	const CATEGORY_ICONS: Record<string, string> = {
		structure: 'stack',
		volume: 'chart-bar',
		options_gamma: 'chart-line-up',
		volatility: 'wave-sine',
		catalyst: 'lightning',
		ml: 'brain'
	};

	function categoryLabel(category: string): string {
		return CATEGORY_LABELS[category] ?? category;
	}

	function categoryIcon(category: string): string {
		return CATEGORY_ICONS[category] ?? 'crosshair';
	}

	/** Distinct categories present in the catalogue, in a stable preferred order. */
	function categoriesOf(scanners: Scanner[]): string[] {
		const order = ['structure', 'volume', 'options_gamma', 'volatility', 'catalyst', 'ml'];
		const present = new Set(scanners.map((s) => s.category ?? 'other'));
		const ordered = order.filter((c) => present.has(c));
		const extras = [...present].filter((c) => !order.includes(c)).sort();
		return [...ordered, ...extras];
	}

	/** Apply the category + search filters, then group the survivors by category. */
	function groupedScanners(scanners: Scanner[]): { category: string; items: Scanner[] }[] {
		const q = searchQuery.trim().toLowerCase();
		const matches = scanners.filter((s) => {
			if (categoryFilter && (s.category ?? 'other') !== categoryFilter) return false;
			if (!q) return true;
			return (
				s.name.toLowerCase().includes(q) ||
				s.description.toLowerCase().includes(q) ||
				s.scanner_id.toLowerCase().includes(q)
			);
		});
		const groups: { category: string; items: Scanner[] }[] = [];
		for (const category of categoriesOf(matches)) {
			const items = matches.filter((s) => (s.category ?? 'other') === category);
			if (items.length > 0) groups.push({ category, items });
		}
		return groups;
	}

	async function submit(scanners: Scanner[]): Promise<void> {
		errorMessage = null;
		const selected = scanners.find((s) => s.scanner_id === builder.scannerId);
		if (!selected) {
			errorMessage = 'Select a scanner first.';
			return;
		}
		if (symbols.length === 0) {
			errorMessage = 'Enter at least one symbol.';
			return;
		}

		submitting = true;
		try {
			const { run_id } = await runScan({
				scanner_id: builder.scannerId,
				symbols,
				timeframe: builder.timeframe,
				history: builder.history,
				params: { ...builder.params }
			});
			await goto(`/results?run=${encodeURIComponent(run_id)}`);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to start scan.';
		} finally {
			submitting = false;
		}
	}

	function numberValue(value: unknown): number | undefined {
		return typeof value === 'number' ? value : undefined;
	}

	function stringValue(value: unknown): string {
		return value === undefined || value === null ? '' : String(value);
	}

	function boolValue(value: unknown): boolean {
		return value === true;
	}
</script>

<svelte:head>
	<title>Scanner Builder · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-5xl">
	<header class="mb-6">
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="scan" class="text-accent" />
			Scanner Builder
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Configure a scan against the engine and dispatch it to the run queue.
		</p>
	</header>

	{#snippet builderForm(scanners: Scanner[])}
		{@const selected = scanners.find((s) => s.scanner_id === builder.scannerId)}
		{@const groups = groupedScanners(scanners)}
		<div class="grid gap-6 lg:grid-cols-[18rem_1fr]">
			<!-- Scanner picker -->
			<aside class="space-y-3">
				<div class="flex items-center justify-between">
					<h2 class="text-xs font-medium tracking-wide text-base-400 uppercase">Scanner</h2>
					<span class="text-[11px] text-base-500">{scanners.length} total</span>
				</div>

				<!-- Category filter + search -->
				<div class="space-y-2">
					<label class="block">
						<span class="mb-1 flex items-center gap-1.5 text-[11px] text-base-500">
							<Icon name="funnel" />
							Category
						</span>
						<select
							bind:value={categoryFilter}
							class="w-full rounded-md border border-base-700 bg-base-900 px-2.5 py-1.5 text-xs text-base-100 outline-none focus:border-accent"
						>
							<option value="">All categories</option>
							{#each categoriesOf(scanners) as category (category)}
								<option value={category}>{categoryLabel(category)}</option>
							{/each}
						</select>
					</label>
					<input
						type="text"
						bind:value={searchQuery}
						placeholder="Search scanners…"
						class="w-full rounded-md border border-base-700 bg-base-900 px-2.5 py-1.5 text-xs text-base-100 outline-none focus:border-accent"
					/>
				</div>

				{#if groups.length === 0}
					<p class="text-sm text-base-500">No scanners match your filters.</p>
				{:else}
					<div class="space-y-4">
						{#each groups as group (group.category)}
							<div class="space-y-2">
								<h3
									class="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-base-500 uppercase"
								>
									<Icon name={categoryIcon(group.category)} class="text-accent" />
									{categoryLabel(group.category)}
									<span class="font-normal text-base-600">({group.items.length})</span>
								</h3>
								{#each group.items as scanner (scanner.scanner_id)}
									<button
										type="button"
										onclick={() => selectScanner(scanner)}
										class="w-full rounded-lg border p-3 text-left transition-colors"
										class:border-accent={builder.scannerId === scanner.scanner_id}
										class:bg-base-850={builder.scannerId === scanner.scanner_id}
										class:border-base-700={builder.scannerId !== scanner.scanner_id}
										class:hover:border-base-600={builder.scannerId !== scanner.scanner_id}
									>
										<div class="flex items-center gap-2 text-sm font-semibold text-base-100">
											<Icon name="crosshair" class="text-accent" />
											{scanner.name}
										</div>
										<p class="mt-1 line-clamp-2 text-xs text-base-400">{scanner.description}</p>
									</button>
								{/each}
							</div>
						{/each}
					</div>
				{/if}
			</aside>

			<!-- Config form -->
			<section class="space-y-5 rounded-lg border border-base-700 bg-base-850 p-5">
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">Symbols</span>
						<input
							type="text"
							bind:value={builder.symbolsInput}
							placeholder="SPY, QQQ, AAPL"
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
						/>
						<span class="mt-1 block text-[11px] text-base-500">
							{symbols.length} symbol{symbols.length === 1 ? '' : 's'} parsed
						</span>
					</label>

					<div class="grid grid-cols-2 gap-3">
						<label class="block">
							<span class="mb-1 block text-xs font-medium text-base-300">Timeframe</span>
							<select
								bind:value={builder.timeframe}
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
								bind:value={builder.history}
								class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
							>
								{#each HISTORY_WINDOWS as hw (hw)}
									<option value={hw}>{hw}</option>
								{/each}
							</select>
						</label>
					</div>
				</div>

				<!-- Dynamic params from scanner schema -->
				{#if selected}
					{@const props = selected.params_schema?.properties ?? {}}
					{#if Object.keys(props).length > 0}
						<div>
							<h3 class="mb-2 flex items-center gap-1.5 text-xs font-medium text-base-300">
								<Icon name="sliders-horizontal" />
								Parameters
							</h3>
							<div class="grid gap-3 sm:grid-cols-2">
								{#each Object.entries(props) as [key, schema] (key)}
									{@const field = schema as JsonSchemaProperty}
									<label class="block">
										<span class="mb-1 block text-xs text-base-400">
											{field.title ?? key}
										</span>
										{#if field.enum && field.enum.length > 0}
											<select
												value={stringValue(builder.params[key])}
												onchange={(e) => setParam(key, e.currentTarget.value)}
												class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
											>
												{#each field.enum as option (option)}
													<option value={String(option)}>{option}</option>
												{/each}
											</select>
										{:else if field.type === 'boolean'}
											<input
												type="checkbox"
												checked={boolValue(builder.params[key])}
												onchange={(e) => setParam(key, e.currentTarget.checked)}
												class="h-4 w-4 rounded border-base-700 bg-base-900 accent-accent"
											/>
										{:else if field.type === 'number' || field.type === 'integer'}
											<input
												type="number"
												value={numberValue(builder.params[key]) ?? ''}
												min={field.minimum}
												max={field.maximum}
												oninput={(e) => setParam(key, e.currentTarget.valueAsNumber)}
												class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
											/>
										{:else}
											<input
												type="text"
												value={stringValue(builder.params[key])}
												oninput={(e) => setParam(key, e.currentTarget.value)}
												class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
											/>
										{/if}
										{#if field.description}
											<span class="mt-1 block text-[11px] text-base-500">{field.description}</span>
										{/if}
									</label>
								{/each}
							</div>
						</div>
					{/if}
				{:else}
					<p
						class="rounded-md border border-dashed border-base-700 p-4 text-center text-sm text-base-500"
					>
						Pick a scanner to configure its parameters.
					</p>
				{/if}

				{#if errorMessage}
					<p class="flex items-center gap-1.5 text-sm text-danger">
						<Icon name="warning-circle" />
						{errorMessage}
					</p>
				{/if}

				<div class="flex items-center justify-end gap-3 border-t border-base-800 pt-4">
					<button
						type="button"
						onclick={() => submit(scanners)}
						disabled={submitting || !builder.scannerId}
						class="flex items-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
					>
						{#if submitting}
							<Icon name="spinner-gap" class="animate-spin" />
							Dispatching…
						{:else}
							<Icon name="play" />
							Run Scan
						{/if}
					</button>
				</div>
			</section>
		</div>
	{/snippet}

	<svelte:boundary>
		{#snippet pending()}
			<div class="h-96 animate-pulse rounded-lg border border-base-700 bg-base-850"></div>
		{/snippet}

		{@render builderForm(await listScanners())}

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
</div>
