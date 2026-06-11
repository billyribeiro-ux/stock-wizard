<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import VendorKeyRow from '$lib/components/VendorKeyRow.svelte';
	import { listVendors, addVendorKey } from './data.remote';
	import type { Vendor } from '$lib/types';

	const VENDOR_OPTIONS = ['polygon', 'tradier', 'alpaca', 'databento', 'finnhub', 'custom'];
	const SCOPE_OPTIONS = ['market-data', 'options', 'fundamentals', 'news', 'trading'];

	function selectedScopes(): string[] {
		const value = addVendorKey.fields.scopes.value();
		return Array.isArray(value) ? (value as string[]) : [];
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
			Manage vendor API keys used by the engine to source market data.
		</p>
	</header>

	<!-- Add key -->
	<section class="rounded-lg border border-base-700 bg-base-850 p-5">
		<h2 class="mb-4 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="key" class="text-accent" />
			Add a vendor key
		</h2>

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
						{#each VENDOR_OPTIONS as vendor (vendor)}
							<option value={vendor}>{vendor}</option>
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
						placeholder="e.g. Polygon prod"
						class="w-full rounded-md border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus:border-accent"
					/>
					{#each addVendorKey.fields.label.issues() as issue, i (i)}
						<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
					{/each}
				</label>
			</div>

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
							<input {...addVendorKey.fields.scopes.as('checkbox', scope)} class="accent-accent" />
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
	</section>

	<!-- Existing keys -->
	<section>
		<h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-base-100">
			<Icon name="list-bullets" class="text-accent" />
			Configured keys
		</h2>

		{#snippet vendorList(vendors: Vendor[])}
			{#if vendors.length === 0}
				<div
					class="flex h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-base-700 text-sm text-base-500"
				>
					<Icon name="key" class="text-2xl" />
					No vendor keys configured yet.
				</div>
			{:else}
				<div class="space-y-2">
					{#each vendors as vendor (vendor.id)}
						<VendorKeyRow {vendor} />
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

			{@render vendorList(await listVendors())}

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
