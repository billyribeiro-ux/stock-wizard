<script lang="ts">
	import Icon from './Icon.svelte';
	import { setVendorEnabled, removeVendorKey } from '../../routes/settings/data.remote';
	import type { Vendor } from '$lib/types';

	interface Props {
		vendor: Vendor;
	}

	let { vendor }: Props = $props();

	let busy = $state(false);

	async function toggle(): Promise<void> {
		busy = true;
		try {
			await setVendorEnabled({ id: vendor.id, enabled: !vendor.enabled });
		} finally {
			busy = false;
		}
	}

	async function remove(): Promise<void> {
		busy = true;
		try {
			await removeVendorKey(vendor.id);
		} finally {
			busy = false;
		}
	}

	function lastUsed(iso: string | null | undefined): string {
		if (!iso) return 'never used';
		const date = new Date(iso);
		return Number.isNaN(date.getTime()) ? iso : `used ${date.toLocaleDateString()}`;
	}
</script>

<div
	class="flex items-center gap-4 rounded-lg border border-base-700 bg-base-850 px-4 py-3"
	class:opacity-60={!vendor.enabled}
>
	<Icon name="key" class="text-lg text-accent" />

	<div class="min-w-0 flex-1">
		<div class="flex items-center gap-2">
			<span class="truncate text-sm font-semibold text-base-100">{vendor.label}</span>
			<span class="rounded bg-base-800 px-1.5 py-0.5 text-[11px] text-base-300">
				{vendor.vendor}
			</span>
		</div>
		<div class="mt-0.5 flex items-center gap-3 text-xs text-base-400">
			<span class="font-mono">{vendor.masked_key}</span>
			<span>{lastUsed(vendor.last_used_at)}</span>
		</div>
		{#if vendor.scopes.length > 0}
			<div class="mt-1 flex flex-wrap gap-1">
				{#each vendor.scopes as scope (scope)}
					<span class="rounded bg-base-900 px-1.5 py-0.5 text-[10px] text-base-400">{scope}</span>
				{/each}
			</div>
		{/if}
	</div>

	<button
		type="button"
		onclick={toggle}
		disabled={busy}
		class="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
		class:bg-long-soft={vendor.enabled}
		class:text-long={vendor.enabled}
		class:bg-base-800={!vendor.enabled}
		class:text-base-300={!vendor.enabled}
	>
		<Icon name={vendor.enabled ? 'plugs-connected' : 'plug'} />
		{vendor.enabled ? 'Enabled' : 'Disabled'}
	</button>

	<button
		type="button"
		onclick={remove}
		disabled={busy}
		class="rounded-md p-1.5 text-base-400 transition-colors hover:bg-short-soft hover:text-short disabled:opacity-50"
		aria-label="Delete key"
	>
		<Icon name="trash" />
	</button>
</div>
