<script lang="ts">
	import Icon from './Icon.svelte';
	import {
		setVendorEnabled,
		removeVendorKey,
		renameVendorKey,
		rotateVendorKey
	} from '../../routes/settings/data.remote';
	import type { Vendor } from '$lib/types';

	interface Props {
		vendor: Vendor;
	}

	let { vendor }: Props = $props();

	let busy = $state(false);
	let confirmingDelete = $state(false);
	let renaming = $state(false);
	let renameValue = $state(vendor.label);
	let rotating = $state(false);

	const rotate = $derived(rotateVendorKey.for(vendor.id));

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
			confirmingDelete = false;
		}
	}

	function startRename(): void {
		renameValue = vendor.label;
		renaming = true;
	}

	async function saveRename(): Promise<void> {
		const label = renameValue.trim();
		if (!label || label === vendor.label) {
			renaming = false;
			return;
		}
		busy = true;
		try {
			await renameVendorKey({ id: vendor.id, label });
		} finally {
			busy = false;
			renaming = false;
		}
	}

	function lastUsed(iso: string | null | undefined): string {
		if (!iso) return 'never used';
		const date = new Date(iso);
		return Number.isNaN(date.getTime()) ? iso : `used ${date.toLocaleDateString()}`;
	}
</script>

<div
	class="rounded-lg border bg-base-850 px-4 py-3"
	class:border-long={vendor.enabled}
	class:border-base-700={!vendor.enabled}
	class:opacity-60={!vendor.enabled}
>
	<div class="flex items-center gap-4">
		<Icon name="key" class="text-lg text-accent" />

		<div class="min-w-0 flex-1">
			<div class="flex items-center gap-2">
				{#if renaming}
					<input
						bind:value={renameValue}
						onkeydown={(e) => {
							if (e.key === 'Enter') saveRename();
							if (e.key === 'Escape') renaming = false;
						}}
						disabled={busy}
						aria-label="Key label"
						class="min-w-0 flex-1 rounded-md border border-accent bg-base-900 px-2 py-1 text-sm text-base-100 outline-none"
					/>
					<button
						type="button"
						onclick={saveRename}
						disabled={busy}
						class="rounded-md bg-accent-strong px-2 py-1 text-xs font-semibold text-base-950 disabled:opacity-50"
					>
						Save
					</button>
					<button
						type="button"
						onclick={() => (renaming = false)}
						class="rounded-md px-2 py-1 text-xs text-base-400 hover:text-base-200"
					>
						Cancel
					</button>
				{:else}
					<span class="truncate text-sm font-semibold text-base-100">{vendor.label}</span>
					{#if vendor.enabled}
						<span class="rounded bg-long-soft px-1.5 py-0.5 text-[10px] font-medium text-long">
							active
						</span>
					{/if}
					{#if vendor.key_version != null}
						<span class="rounded bg-base-800 px-1.5 py-0.5 text-[10px] text-base-400">
							v{vendor.key_version}
						</span>
					{/if}
				{/if}
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
			aria-label={vendor.enabled ? 'Disable key' : 'Enable key'}
		>
			<Icon name={vendor.enabled ? 'plugs-connected' : 'plug'} />
			{vendor.enabled ? 'Enabled' : 'Disabled'}
		</button>

		<button
			type="button"
			onclick={() => (rotating = !rotating)}
			disabled={busy}
			class="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs text-base-300 transition-colors hover:bg-base-800 hover:text-base-100 disabled:opacity-50"
			aria-label="Rotate key secret"
		>
			<Icon name="arrows-clockwise" />
			Rotate
		</button>

		<button
			type="button"
			onclick={startRename}
			disabled={busy || renaming}
			class="rounded-md p-1.5 text-base-400 transition-colors hover:bg-base-800 hover:text-base-100 disabled:opacity-50"
			aria-label="Rename key"
		>
			<Icon name="pencil-simple" />
		</button>

		{#if confirmingDelete}
			<div class="flex items-center gap-1">
				<button
					type="button"
					onclick={remove}
					disabled={busy}
					class="rounded-md bg-short-soft px-2 py-1.5 text-xs font-medium text-short disabled:opacity-50"
				>
					Confirm
				</button>
				<button
					type="button"
					onclick={() => (confirmingDelete = false)}
					class="rounded-md px-2 py-1.5 text-xs text-base-400 hover:text-base-200"
				>
					Cancel
				</button>
			</div>
		{:else}
			<button
				type="button"
				onclick={() => (confirmingDelete = true)}
				disabled={busy}
				class="rounded-md p-1.5 text-base-400 transition-colors hover:bg-short-soft hover:text-short disabled:opacity-50"
				aria-label="Delete key"
			>
				<Icon name="trash" />
			</button>
		{/if}
	</div>

	{#if rotating}
		<form
			{...rotate.enhance(async ({ form, submit }) => {
				try {
					if (await submit()) {
						form.reset();
						rotating = false;
					}
				} catch {
					// surfaced via issues()
				}
			})}
			class="mt-3 flex items-center gap-2 border-t border-base-800 pt-3"
		>
			<input {...rotate.fields.id.as('hidden', vendor.id)} />
			<input
				{...rotate.fields._api_key.as('password')}
				placeholder="New secret for {vendor.label}…"
				autocomplete="off"
				class="min-w-0 flex-1 rounded-md border border-base-700 bg-base-900 px-3 py-2 font-mono text-xs text-base-100 outline-none focus:border-accent"
			/>
			<button
				type="submit"
				class="flex items-center gap-1.5 rounded-md bg-accent-strong px-3 py-2 text-xs font-semibold text-base-950 transition-colors hover:bg-accent"
			>
				<Icon name="arrows-clockwise" />
				Replace
			</button>
			<button
				type="button"
				onclick={() => (rotating = false)}
				class="rounded-md px-2 py-2 text-xs text-base-400 hover:text-base-200"
			>
				Cancel
			</button>
		</form>
		{#each rotate.fields._api_key.issues() as issue, i (i)}
			<span class="mt-1 block text-[11px] text-danger">{issue.message}</span>
		{/each}
		{#if rotate.result?.success}
			<span class="mt-1 block text-[11px] text-ok">Secret rotated (now v{rotate.result.key_version}).</span>
		{/if}
	{/if}
</div>
