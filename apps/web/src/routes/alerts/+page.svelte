<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import {
		createRule,
		listEvents,
		listRules,
		listScanners,
		removeRule,
		setRuleEnabled
	} from './data.remote';
	import type { AlertEvent, AlertRule, Scanner, Side } from '$lib/types';

	const SIDE_OPTIONS = ['LONG', 'SHORT'] as const;
	const CHANNEL_OPTIONS = ['log', 'webhook', 'email'] as const;

	// --- Create-rule form state ------------------------------------------------
	let name = $state('');
	let selectedScanners = $state<string[]>([]);
	let symbolsText = $state('');
	let sides = $state<('LONG' | 'SHORT')[]>(['LONG']);
	let minScore = $state(0.6);
	let channel = $state<'log' | 'webhook' | 'email'>('log');
	let target = $state('');

	let submitting = $state(false);
	let errorMessage = $state<string | null>(null);
	let createdId = $state<string | null>(null);

	/** id of the rule currently being toggled/deleted, to disable its buttons */
	let busyRuleId = $state<string | null>(null);

	function toggleScanner(id: string): void {
		selectedScanners = selectedScanners.includes(id)
			? selectedScanners.filter((s) => s !== id)
			: [...selectedScanners, id];
	}

	function toggleSide(side: 'LONG' | 'SHORT'): void {
		sides = sides.includes(side) ? sides.filter((s) => s !== side) : [...sides, side];
	}

	async function submit(): Promise<void> {
		errorMessage = null;
		createdId = null;

		const symbols = symbolsText
			.split(',')
			.map((s) => s.trim().toUpperCase())
			.filter((s) => s.length > 0);

		if (!name.trim()) {
			errorMessage = 'Give the rule a name.';
			return;
		}
		if (sides.length === 0) {
			errorMessage = 'Pick at least one side.';
			return;
		}
		if (channel !== 'log' && !target.trim()) {
			errorMessage = `Provide a ${channel === 'email' ? 'recipient address' : 'webhook URL'} target.`;
			return;
		}

		submitting = true;
		try {
			const { id } = await createRule({
				name: name.trim(),
				scanner_ids: selectedScanners,
				symbols,
				sides,
				classifications: [],
				min_score: minScore,
				channel,
				target: channel === 'log' ? '' : target.trim(),
				cooldown_seconds: 300
			});
			createdId = id;
			name = '';
			selectedScanners = [];
			symbolsText = '';
			sides = ['LONG'];
			minScore = 0.6;
			channel = 'log';
			target = '';
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to create rule.';
		} finally {
			submitting = false;
		}
	}

	async function toggleRule(rule: AlertRule): Promise<void> {
		busyRuleId = rule.id;
		try {
			await setRuleEnabled({ id: rule.id, enabled: !rule.enabled });
		} finally {
			busyRuleId = null;
		}
	}

	async function deleteRule(rule: AlertRule): Promise<void> {
		busyRuleId = rule.id;
		try {
			await removeRule(rule.id);
		} finally {
			busyRuleId = null;
		}
	}

	function sideMeta(side: Side): { tone: string; bg: string } {
		if (side === 'LONG') return { tone: 'text-long', bg: 'bg-long-soft' };
		if (side === 'SHORT') return { tone: 'text-short', bg: 'bg-short-soft' };
		return { tone: 'text-neutral-signal', bg: 'bg-base-800' };
	}

	function fmtTs(ts: string): string {
		const d = new Date(ts);
		return Number.isNaN(d.getTime()) ? ts : d.toLocaleString();
	}

	function ruleName(rules: AlertRule[], ruleId: string): string {
		return rules.find((r) => r.id === ruleId)?.name ?? ruleId;
	}
</script>

<svelte:head>
	<title>Alerts · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-5xl space-y-8">
	<header>
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="bell" class="text-accent" />
			Alerts
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Route high-conviction signals to a log, webhook, or your inbox.
		</p>
	</header>

	<!-- Create rule -->
	<section class="rounded-lg border border-base-700 bg-base-850 p-5">
		<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="plus" class="text-accent" />
			Create an alert rule
		</h2>

		<div class="space-y-4">
			<div class="grid gap-4 sm:grid-cols-2">
				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">Name</span>
					<input
						type="text"
						bind:value={name}
						placeholder="e.g. SPY breakouts"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
					/>
				</label>

				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">Symbols</span>
					<input
						type="text"
						bind:value={symbolsText}
						placeholder="SPY, QQQ, NVDA (empty = all)"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
				</label>
			</div>

			<div>
				<span class="mb-2 block text-xs font-medium text-base-300">
					Scanners <span class="text-base-500">(empty = all)</span>
				</span>
				{#snippet scannerPicker(scanners: Scanner[])}
					<div class="flex flex-wrap gap-2">
						{#each scanners as scanner (scanner.scanner_id)}
							<label
								class="flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors"
								class:border-accent={selectedScanners.includes(scanner.scanner_id)}
								class:text-accent={selectedScanners.includes(scanner.scanner_id)}
								class:border-base-700={!selectedScanners.includes(scanner.scanner_id)}
								class:text-base-300={!selectedScanners.includes(scanner.scanner_id)}
							>
								<input
									type="checkbox"
									checked={selectedScanners.includes(scanner.scanner_id)}
									onchange={() => toggleScanner(scanner.scanner_id)}
									class="accent-accent"
								/>
								{scanner.name}
							</label>
						{:else}
							<span class="text-xs text-base-500">No scanners available.</span>
						{/each}
					</div>
				{/snippet}

				<svelte:boundary>
					{#snippet pending()}
						<div class="h-9 animate-pulse rounded-md bg-base-900"></div>
					{/snippet}

					{@render scannerPicker(await listScanners())}

					{#snippet failed(error, reset)}
						<p class="flex items-center gap-1.5 text-xs text-danger">
							<Icon name="warning-circle" />
							{error instanceof Error ? error.message : 'Failed to load scanners.'}
							<button type="button" onclick={reset} class="underline">retry</button>
						</p>
					{/snippet}
				</svelte:boundary>
			</div>

			<div class="grid gap-4 sm:grid-cols-3">
				<div>
					<span class="mb-2 block text-xs font-medium text-base-300">Sides</span>
					<div class="flex gap-2">
						{#each SIDE_OPTIONS as side (side)}
							<label
								class="flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors"
								class:border-accent={sides.includes(side)}
								class:border-base-700={!sides.includes(side)}
								class:text-long={side === 'LONG'}
								class:text-short={side === 'SHORT'}
							>
								<input
									type="checkbox"
									checked={sides.includes(side)}
									onchange={() => toggleSide(side)}
									class="accent-accent"
								/>
								{side}
							</label>
						{/each}
					</div>
				</div>

				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">
						Min score
						<span class="ml-1 font-mono text-accent">{minScore.toFixed(2)}</span>
					</span>
					<input
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={minScore}
						class="mt-2 w-full accent-accent"
					/>
				</label>

				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">Channel</span>
					<select
						bind:value={channel}
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
					>
						{#each CHANNEL_OPTIONS as option (option)}
							<option value={option}>{option}</option>
						{/each}
					</select>
				</label>
			</div>

			{#if channel !== 'log'}
				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">
						{channel === 'email' ? 'Recipient address' : 'Webhook URL'}
					</span>
					<input
						type="text"
						bind:value={target}
						placeholder={channel === 'email' ? 'alerts@example.com' : 'https://hooks.example.com/…'}
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
				</label>
			{/if}

			{#if errorMessage}
				<p class="flex items-center gap-1.5 text-sm text-danger">
					<Icon name="warning-circle" />
					{errorMessage}
				</p>
			{/if}

			{#if createdId}
				<p class="flex items-center gap-1.5 text-sm text-ok">
					<Icon name="check-circle" />
					Rule created.
				</p>
			{/if}

			<div class="flex justify-end border-t border-base-800 pt-4">
				<button
					type="button"
					onclick={submit}
					disabled={submitting}
					class="flex items-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
				>
					{#if submitting}
						<Icon name="spinner-gap" class="animate-spin" />
						Saving…
					{:else}
						<Icon name="floppy-disk" />
						Save rule
					{/if}
				</button>
			</div>
		</div>
	</section>

	<!-- Configured rules -->
	<section>
		<h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="list-bullets" class="text-accent" />
			Configured rules
		</h2>

		{#snippet ruleList(rules: AlertRule[])}
			{#if rules.length === 0}
				<div
					class="flex h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-base-700 text-sm text-base-500"
				>
					<Icon name="bell" class="text-2xl" />
					No alert rules configured yet.
				</div>
			{:else}
				<div class="space-y-2">
					{#each rules as rule (rule.id)}
						<div
							class="flex items-center gap-4 rounded-lg border border-base-700 bg-base-850 px-4 py-3"
							class:opacity-60={!rule.enabled}
						>
							<Icon name="bell" class="text-lg text-accent" />

							<div class="min-w-0 flex-1">
								<div class="flex items-center gap-2">
									<span class="truncate text-sm font-semibold text-base-100">{rule.name}</span>
									<span class="rounded bg-base-800 px-1.5 py-0.5 text-[11px] text-base-300">
										{rule.channel}{rule.target ? ` → ${rule.target}` : ''}
									</span>
								</div>
								<div class="mt-0.5 flex flex-wrap items-center gap-3 text-xs text-base-400">
									<span class="font-mono">
										{rule.symbols.length > 0 ? rule.symbols.join(', ') : 'all symbols'}
									</span>
									<span>
										{rule.scanner_ids.length > 0 ? rule.scanner_ids.join(', ') : 'all scanners'}
									</span>
									<span>
										score ≥ <span class="font-mono text-accent">{rule.min_score.toFixed(2)}</span>
									</span>
								</div>
								{#if rule.sides.length > 0}
									<div class="mt-1 flex flex-wrap gap-1">
										{#each rule.sides as side (side)}
											<span
												class="rounded px-1.5 py-0.5 text-[10px] font-bold {sideMeta(side)
													.tone} {sideMeta(side).bg}"
											>
												{side}
											</span>
										{/each}
									</div>
								{/if}
							</div>

							<button
								type="button"
								onclick={() => toggleRule(rule)}
								disabled={busyRuleId === rule.id}
								class="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
								class:bg-long-soft={rule.enabled}
								class:text-long={rule.enabled}
								class:bg-base-800={!rule.enabled}
								class:text-base-300={!rule.enabled}
							>
								<Icon name={rule.enabled ? 'toggle-right' : 'toggle-left'} />
								{rule.enabled ? 'Enabled' : 'Disabled'}
							</button>

							<button
								type="button"
								onclick={() => deleteRule(rule)}
								disabled={busyRuleId === rule.id}
								class="rounded-md p-1.5 text-base-400 transition-colors hover:bg-short-soft hover:text-short disabled:opacity-50"
								aria-label="Delete rule"
							>
								<Icon name="trash" />
							</button>
						</div>
					{/each}
				</div>
			{/if}
		{/snippet}

		<svelte:boundary>
			{#snippet pending()}
				<div class="space-y-2">
					<div class="h-16 animate-pulse rounded-lg bg-base-850"></div>
					<div class="h-16 animate-pulse rounded-lg bg-base-850"></div>
				</div>
			{/snippet}

			{@render ruleList(await listRules())}

			{#snippet failed(error, reset)}
				<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center text-sm">
					<Icon name="warning-circle" class="text-2xl text-danger" />
					<p class="mt-2 text-base-200">
						{error instanceof Error ? error.message : 'Failed to load alert rules.'}
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
	</section>

	<!-- Alert history -->
	<section>
		<header class="mb-3 flex items-center justify-between">
			<h2 class="flex items-center gap-2 text-sm font-semibold text-base-100">
				<Icon name="clock-counter-clockwise" class="text-accent" />
				Alert history
			</h2>
			<button
				type="button"
				onclick={() => listEvents().refresh()}
				class="flex items-center gap-1 text-xs text-base-400 hover:text-base-200"
			>
				<Icon name="clock-clockwise" />
				refresh
			</button>
		</header>

		{#snippet eventTable(events: AlertEvent[], rules: AlertRule[])}
			{#if events.length === 0}
				<div
					class="flex h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-base-700 text-sm text-base-500"
				>
					<Icon name="bell" class="text-2xl" />
					No alerts have fired yet.
				</div>
			{:else}
				<div class="overflow-x-auto rounded-lg border border-base-700 bg-base-850 p-4">
					<table class="w-full text-xs">
						<thead>
							<tr class="text-left text-base-500">
								<th class="py-1.5 pr-3 font-medium">Time</th>
								<th class="py-1.5 pr-3 font-medium">Rule</th>
								<th class="py-1.5 pr-3 font-medium">Symbol</th>
								<th class="py-1.5 pr-3 font-medium">Side</th>
								<th class="py-1.5 pr-3 font-medium">Scanner</th>
								<th class="py-1.5 pr-3 font-medium">Class</th>
								<th class="py-1.5 pr-3 text-right font-medium">Score</th>
								<th class="py-1.5 pr-3 font-medium">Channel</th>
								<th class="py-1.5 pr-3 text-center font-medium">Delivered</th>
								<th class="py-1.5 font-medium">Message</th>
							</tr>
						</thead>
						<tbody>
							{#each events as event (event.id)}
								<tr class="border-t border-base-800">
									<td class="py-1.5 pr-3 font-mono whitespace-nowrap text-base-300">
										{fmtTs(event.created_at)}
									</td>
									<td class="max-w-32 truncate py-1.5 pr-3 text-base-200">
										{ruleName(rules, event.rule_id)}
									</td>
									<td class="py-1.5 pr-3 font-mono font-semibold text-base-100">{event.symbol}</td>
									<td class="py-1.5 pr-3">
										<span
											class="rounded px-1.5 py-0.5 text-[10px] font-bold {sideMeta(event.side)
												.tone} {sideMeta(event.side).bg}"
										>
											{event.side}
										</span>
									</td>
									<td class="py-1.5 pr-3 text-base-300">{event.scanner_id}</td>
									<td class="py-1.5 pr-3 text-base-300">{event.classification}</td>
									<td class="py-1.5 pr-3 text-right font-mono text-accent">
										{(event.score * 100).toFixed(0)}
									</td>
									<td class="py-1.5 pr-3 text-base-300">{event.channel}</td>
									<td class="py-1.5 pr-3 text-center">
										{#if event.delivered}
											<Icon name="check" class="text-ok" label="Delivered" />
										{:else}
											<span title={event.error ?? 'Delivery failed'}>
												<Icon name="x" class="text-danger" label="Not delivered" />
											</span>
										{/if}
									</td>
									<td class="max-w-64 truncate py-1.5 text-base-400" title={event.message}>
										{event.message}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		{/snippet}

		<svelte:boundary>
			{#snippet pending()}
				<div class="h-32 animate-pulse rounded-lg bg-base-850"></div>
			{/snippet}

			{@render eventTable(await listEvents(), await listRules())}

			{#snippet failed(error, reset)}
				<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center text-sm">
					<Icon name="warning-circle" class="text-2xl text-danger" />
					<p class="mt-2 text-base-200">
						{error instanceof Error ? error.message : 'Failed to load alert history.'}
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
	</section>
</div>
