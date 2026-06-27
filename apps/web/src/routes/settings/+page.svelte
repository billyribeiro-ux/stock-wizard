<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import VendorKeyRow from '$lib/components/VendorKeyRow.svelte';
	import {
		listVendors,
		listVendorCatalog,
		addVendorKey,
		connectSchwab,
		exchangeSchwabCode
	} from './data.remote';
	import type { Vendor, VendorCatalogEntry } from '$lib/types';

	const SCOPE_OPTIONS = ['market-data', 'options', 'fundamentals', 'news', 'trading'];

	// Schwab OAuth flow: connect (step 1) yields an authorize URL + credential id we
	// carry into the token exchange (step 2).
	let schwabAuthUrl = $state('');
	let schwabKeyId = $state('');
	let schwabConnected = $state(false);

	function selectedScopes(): string[] {
		const value = addVendorKey.fields.scopes.value();
		return Array.isArray(value) ? (value as string[]) : [];
	}

	/** Group stored keys by vendor so each vendor can hold several keys. */
	function groupByVendor(
		vendors: Vendor[],
		catalog: VendorCatalogEntry[]
	): { vendor: string; label: string; entry?: VendorCatalogEntry; keys: Vendor[] }[] {
		// Plain records (not reactive Maps) — this is a pure, throwaway grouping computation.
		const catalogByVendor: Record<string, VendorCatalogEntry> = {};
		for (const c of catalog) catalogByVendor[c.vendor] = c;
		const groups: Record<string, Vendor[]> = {};
		for (const v of vendors) (groups[v.vendor] ??= []).push(v);
		return Object.entries(groups)
			.map(([vendor, keys]) => {
				const entry = catalogByVendor[vendor];
				return { vendor, label: entry?.label ?? keys[0]?.label ?? vendor, entry, keys };
			})
			.sort((a, b) => {
				// FMP (primary equity feed) first, then alphabetical by label
				if (a.vendor === 'fmp') return -1;
				if (b.vendor === 'fmp') return 1;
				return a.label.localeCompare(b.label);
			});
	}
</script>

<svelte:head>
	<title>Settings · Stock Wizard</title>
</svelte:head>

<div class="mx-auto max-w-3xl space-y-8">
	<header>
		<h1 class="flex items-center gap-2 text-xl font-bold text-base-50">
			<Icon name="gear-six" class="text-accent" />
			Settings
		</h1>
		<p class="mt-1 text-sm text-base-400">
			Manage vendor API keys used by the engine to source market data. Add multiple keys per vendor,
			rotate secrets in place, and swap which key is active.
		</p>
	</header>

	<!-- Add key -->
	<section class="rounded-lg border border-base-700 bg-base-850 p-5">
		<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="key" class="text-accent" />
			Add a vendor key
		</h2>

		{#snippet addForm(catalog: VendorCatalogEntry[])}
			{@const selectedVendor = addVendorKey.fields.vendor.value()}
			{@const activeEntry = catalog.find((c) => c.vendor === selectedVendor)}
			<form
				{...addVendorKey.enhance(async (form) => {
					try {
						if (await form.submit()) {
							form.element.reset();
						}
					} catch {
						// surfaced via fields.allIssues()
					}
				})}
				class="space-y-4"
			>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">Vendor</span>
						<select
							{...addVendorKey.fields.vendor.as('select')}
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
						>
							{#each catalog as entry (entry.vendor)}
								<option value={entry.vendor}>
									{entry.label}{entry.vendor === 'fmp' ? ' — primary equity feed' : ''}
								</option>
							{/each}
						</select>
						{#each addVendorKey.fields.vendor.issues() as issue, i (i)}
							<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
						{/each}
					</label>

					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">Label</span>
						<input
							{...addVendorKey.fields.label.as('text')}
							placeholder="e.g. FMP live"
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
						/>
						{#each addVendorKey.fields.label.issues() as issue, i (i)}
							<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
						{/each}
					</label>
				</div>

				{#if activeEntry}
					<div class="rounded-md border border-base-800 bg-base-900 px-3 py-2 text-xs">
						<div class="flex flex-wrap items-center gap-2">
							<span class="font-semibold text-base-200">{activeEntry.label}</span>
							{#if activeEntry.vendor === 'fmp'}
								<span
									class="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-medium text-accent"
								>
									Primary equity data feed
								</span>
							{/if}
							{#if activeEntry.requires_key}
								<span class="rounded bg-base-800 px-1.5 py-0.5 text-[10px] text-base-300">
									needs key
								</span>
							{:else}
								<span class="rounded bg-base-800 px-1.5 py-0.5 text-[10px] text-base-400">
									key optional
								</span>
							{/if}
						</div>
						{#if activeEntry.capabilities.length > 0}
							<div class="mt-1.5 flex flex-wrap gap-1">
								{#each activeEntry.capabilities as cap (cap)}
									<span class="rounded bg-base-800 px-1.5 py-0.5 text-[10px] text-base-400">
										{cap}
									</span>
								{/each}
							</div>
						{/if}
						{#if activeEntry.notes}
							<p class="mt-1.5 text-[11px] text-base-500">{activeEntry.notes}</p>
						{/if}
						{#if activeEntry.docs_url}
							<a
								href={activeEntry.docs_url}
								target="_blank"
								rel="noopener noreferrer"
								class="mt-1.5 inline-flex items-center gap-1 text-[11px] text-accent hover:underline"
							>
								<Icon name="arrow-square-out" />
								docs
							</a>
						{/if}
					</div>
				{/if}

				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">API key</span>
					<input
						{...addVendorKey.fields._api_key.as('password')}
						placeholder="sk_live_…"
						autocomplete="off"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
					<span class="mt-1 block text-[11px] text-base-500">
						Submitted directly to the server; the plaintext key never lives in the browser bundle.
					</span>
					{#each addVendorKey.fields._api_key.issues() as issue, i (i)}
						<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
					{/each}
				</label>

				<div>
					<span class="mb-2 block text-xs font-medium text-base-300">Scopes</span>
					<div class="flex flex-wrap gap-2">
						{#each SCOPE_OPTIONS as scope (scope)}
							<label
								class="flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors"
								class:border-accent={selectedScopes().includes(scope)}
								class:text-accent={selectedScopes().includes(scope)}
								class:border-base-700={!selectedScopes().includes(scope)}
								class:text-base-300={!selectedScopes().includes(scope)}
							>
								<input
									{...addVendorKey.fields.scopes.as('checkbox', scope)}
									class="accent-accent"
								/>
								{scope}
							</label>
						{/each}
					</div>
				</div>

				{#each addVendorKey.fields.allIssues() as issue, i (i)}
					<p class="flex items-center gap-1.5 text-sm text-danger">
						<Icon name="warning-circle" />
						{issue.message}
					</p>
				{/each}

				{#if addVendorKey.result?.success}
					<p class="flex items-center gap-1.5 text-sm text-ok">
						<Icon name="check-circle" />
						Key added.
					</p>
				{/if}

				<div class="flex justify-end border-t border-base-800 pt-4">
					<button
						type="submit"
						class="flex items-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent"
					>
						<Icon name="floppy-disk" />
						Save key
					</button>
				</div>
			</form>
		{/snippet}

		<svelte:boundary>
			{#snippet pending()}
				<div class="h-40 animate-pulse rounded-md bg-base-900"></div>
			{/snippet}

			{@render addForm(await listVendorCatalog())}

			{#snippet failed(error, reset)}
				<div class="rounded-lg border border-danger/40 bg-base-900 p-6 text-center text-sm">
					<Icon name="warning-circle" class="text-2xl text-danger" />
					<p class="mt-2 text-base-200">
						{error instanceof Error ? error.message : 'Failed to load the vendor catalog.'}
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

	<!-- Charles Schwab OAuth -->
	<section class="rounded-lg border border-base-700 bg-base-850 p-5">
		<h2 class="mb-1 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="plugs-connected" class="text-accent" />
			Connect Charles Schwab
		</h2>
		<p class="mb-4 text-xs text-base-400">
			Schwab uses OAuth2. Enter your app key & secret to get an authorization link, approve it in
			the browser, then paste the URL Schwab redirects you to. Provides real option chains with
			vendor greeks/OI/IV (preferred for the gamma engine) plus equity OHLCV.
		</p>

		<!-- Step 1: app credentials -> authorize URL -->
		<form
			{...connectSchwab.enhance(async (form) => {
				try {
					if (await form.submit()) {
						const result = connectSchwab.result;
						if (result?.success) {
							schwabAuthUrl = result.authorize_url;
							schwabKeyId = result.id;
							schwabConnected = false;
						}
					}
				} catch {
					// surfaced via fields.allIssues()
				}
			})}
			class="space-y-4"
		>
			<div class="grid gap-4 sm:grid-cols-2">
				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">App key</span>
					<input
						{...connectSchwab.fields._app_key.as('password')}
						placeholder="Schwab app key"
						autocomplete="off"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
					{#each connectSchwab.fields._app_key.issues() as issue, i (i)}
						<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
					{/each}
				</label>
				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">App secret</span>
					<input
						{...connectSchwab.fields._app_secret.as('password')}
						placeholder="Schwab app secret"
						autocomplete="off"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
					{#each connectSchwab.fields._app_secret.issues() as issue, i (i)}
						<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
					{/each}
				</label>
			</div>

			<div class="grid gap-4 sm:grid-cols-2">
				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">Redirect URI</span>
					<input
						{...connectSchwab.fields.redirect_uri.as('text')}
						value="https://127.0.0.1:8182"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
					/>
					<span class="mt-1 block text-[11px] text-base-500">
						Must exactly match the callback URL registered on your Schwab app.
					</span>
					{#each connectSchwab.fields.redirect_uri.issues() as issue, i (i)}
						<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
					{/each}
				</label>
				<label class="block">
					<span class="mb-1 block text-xs font-medium text-base-300">Label</span>
					<input
						{...connectSchwab.fields.label.as('text')}
						placeholder="Charles Schwab"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
					/>
				</label>
			</div>

			{#each connectSchwab.fields.allIssues() as issue, i (i)}
				<p class="flex items-center gap-1.5 text-sm text-danger">
					<Icon name="warning-circle" />
					{issue.message}
				</p>
			{/each}

			<div class="flex justify-end">
				<button
					type="submit"
					class="flex items-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent"
				>
					<Icon name="link" />
					Get authorize link
				</button>
			</div>
		</form>

		<!-- Step 2: authorize + paste returned URL -->
		{#if schwabAuthUrl}
			<div class="mt-5 space-y-4 border-t border-base-800 pt-5">
				<div class="rounded-md border border-accent/40 bg-base-900 px-3 py-2 text-xs">
					<p class="text-base-300">1. Open the authorize link, log in, and approve access:</p>
					<a
						href={schwabAuthUrl}
						target="_blank"
						rel="noopener noreferrer"
						class="mt-1.5 inline-flex items-center gap-1 break-all text-[11px] text-accent hover:underline"
					>
						<Icon name="arrow-square-out" />
						{schwabAuthUrl}
					</a>
					<p class="mt-2 text-base-300">
						2. After approving, your browser is redirected to your callback URL. Copy that full URL
						(it contains <code class="text-accent">?code=…</code>) and paste it below.
					</p>
				</div>

				<form
					{...exchangeSchwabCode.enhance(async (form) => {
						try {
							if (await form.submit()) {
								schwabConnected = true;
								schwabAuthUrl = '';
							}
						} catch {
							// surfaced via fields.allIssues()
						}
					})}
					class="space-y-3"
				>
					<input
						type="hidden"
						{...exchangeSchwabCode.fields.key_id.as('text')}
						value={schwabKeyId}
					/>
					<label class="block">
						<span class="mb-1 block text-xs font-medium text-base-300">Redirected URL</span>
						<input
							{...exchangeSchwabCode.fields.redirect_url.as('text')}
							placeholder="https://127.0.0.1:8182/?code=…"
							autocomplete="off"
							class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 outline-none focus:border-accent"
						/>
						{#each exchangeSchwabCode.fields.redirect_url.issues() as issue, i (i)}
							<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
						{/each}
					</label>

					{#each exchangeSchwabCode.fields.allIssues() as issue, i (i)}
						<p class="flex items-center gap-1.5 text-sm text-danger">
							<Icon name="warning-circle" />
							{issue.message}
						</p>
					{/each}

					<div class="flex justify-end">
						<button
							type="submit"
							class="flex items-center gap-2 rounded-md bg-accent-strong px-4 py-2 text-sm font-semibold text-base-950 transition-colors hover:bg-accent"
						>
							<Icon name="check" />
							Complete connection
						</button>
					</div>
				</form>
			</div>
		{/if}

		{#if schwabConnected}
			<p class="mt-4 flex items-center gap-1.5 text-sm text-ok">
				<Icon name="check-circle" />
				Schwab connected — the key is enabled and ready for scans.
			</p>
		{/if}
	</section>

	<!-- Existing keys -->
	<section>
		<h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="list-bullets" class="text-accent" />
			Configured keys
		</h2>

		{#snippet vendorList(vendors: Vendor[], catalog: VendorCatalogEntry[])}
			{#if vendors.length === 0}
				<div
					class="flex h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-base-700 text-sm text-base-500"
				>
					<Icon name="key" class="text-2xl" />
					No vendor keys configured yet.
				</div>
			{:else}
				<div class="space-y-6">
					{#each groupByVendor(vendors, catalog) as group (group.vendor)}
						<div>
							<div class="mb-2 flex items-center gap-2">
								<h3 class="text-sm font-semibold text-base-100">{group.label}</h3>
								<span class="rounded bg-base-800 px-1.5 py-0.5 text-[11px] text-base-300">
									{group.vendor}
								</span>
								{#if group.vendor === 'fmp'}
									<span
										class="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-medium text-accent"
									>
										Primary equity data feed
									</span>
								{/if}
								<span class="text-[11px] text-base-500">
									{group.keys.length}
									{group.keys.length === 1 ? 'key' : 'keys'}
								</span>
							</div>
							{#if group.entry && group.entry.capabilities.length > 0}
								<div class="mb-2 flex flex-wrap gap-1">
									{#each group.entry.capabilities as cap (cap)}
										<span class="rounded bg-base-900 px-1.5 py-0.5 text-[10px] text-base-400">
											{cap}
										</span>
									{/each}
								</div>
							{/if}
							<div class="space-y-2">
								{#each group.keys as vendor (vendor.id)}
									<VendorKeyRow {vendor} />
								{/each}
							</div>
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

			{@render vendorList(await listVendors(), await listVendorCatalog())}

			{#snippet failed(error, reset)}
				<div class="rounded-lg border border-danger/40 bg-base-850 p-6 text-center text-sm">
					<Icon name="warning-circle" class="text-2xl text-danger" />
					<p class="mt-2 text-base-200">
						{error instanceof Error ? error.message : 'Failed to load vendor keys.'}
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
