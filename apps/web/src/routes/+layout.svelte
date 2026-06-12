<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import Icon from '$lib/components/Icon.svelte';
	import { getHealth } from './health.remote';

	let { children } = $props();

	const nav = [
		{ href: '/', label: 'Command Center', icon: 'gauge' },
		{ href: '/scanners', label: 'Scanners', icon: 'scan' },
		{ href: '/results', label: 'Results', icon: 'table' },
		{ href: '/backtest', label: 'Backtest Lab', icon: 'flask' },
		{ href: '/forward', label: 'Forward Test', icon: 'test-tube' },
		{ href: '/ml', label: 'ML Lab', icon: 'brain' },
		{ href: '/portfolio', label: 'Portfolio', icon: 'briefcase' },
		{ href: '/gamma', label: 'SPX Gamma Lab', icon: 'chart-bar' },
		{ href: '/settings', label: 'Settings', icon: 'gear-six' }
	];

	function isActive(href: string): boolean {
		if (href === '/') return page.url.pathname === '/';
		return page.url.pathname.startsWith(href);
	}

	function healthTone(health: {
		status: string;
		data_health: { last_bar_age_seconds: number }[];
	}): {
		tone: string;
		dot: string;
		label: string;
	} {
		const stale = health.data_health.filter((d) => d.last_bar_age_seconds > 600).length;
		const down = health.status?.toLowerCase() !== 'ok' && health.status?.toLowerCase() !== 'up';
		if (down) return { tone: 'text-danger', dot: 'bg-danger', label: 'DEGRADED' };
		if (stale > 0) return { tone: 'text-warn', dot: 'bg-warn', label: `${stale} STALE` };
		return { tone: 'text-ok', dot: 'bg-ok', label: 'OPERATIONAL' };
	}
</script>

<div class="flex h-screen overflow-hidden bg-base-950 text-base-100">
	<!-- Left nav -->
	<aside class="flex w-60 shrink-0 flex-col border-r border-base-800 bg-base-900">
		<div class="flex items-center gap-2 border-b border-base-800 px-5 py-4">
			<Icon name="chart-line" class="text-2xl text-accent" />
			<div class="leading-tight">
				<div class="text-sm font-bold tracking-wide">STOCK WIZARD</div>
				<div class="text-[10px] tracking-widest text-base-500 uppercase">Command Center</div>
			</div>
		</div>

		<nav class="flex-1 space-y-1 p-3">
			{#each nav as item (item.href)}
				<a
					href={item.href}
					class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors"
					class:bg-base-800={isActive(item.href)}
					class:text-base-100={isActive(item.href)}
					class:text-base-400={!isActive(item.href)}
					class:hover:bg-base-850={!isActive(item.href)}
					class:hover:text-base-200={!isActive(item.href)}
					aria-current={isActive(item.href) ? 'page' : undefined}
				>
					<Icon name={item.icon} class="text-lg" />
					{item.label}
				</a>
			{/each}
		</nav>

		<div class="border-t border-base-800 p-3 text-[11px] text-base-500">
			<div class="flex items-center gap-1.5">
				<Icon name="terminal-window" />
				<span>v0.0.1 · dark</span>
			</div>
		</div>
	</aside>

	<!-- Main column -->
	<div class="flex min-w-0 flex-1 flex-col">
		<!-- Top bar -->
		<header
			class="flex h-14 shrink-0 items-center justify-between border-b border-base-800 bg-base-900 px-6"
		>
			<div class="flex items-center gap-2 text-sm text-base-300">
				<Icon name="caret-right" class="text-base-600" />
				<span class="font-medium text-base-100">
					{nav.find((n) => isActive(n.href))?.label ?? 'Dashboard'}
				</span>
			</div>

			<!-- Data-health badge -->
			{#snippet badge(meta: { tone: string; dot: string; label: string })}
				<span
					class="flex items-center gap-2 rounded-full border border-base-700 bg-base-850 px-3 py-1 text-xs font-medium {meta.tone}"
				>
					<span class="h-2 w-2 rounded-full {meta.dot}"></span>
					{meta.label}
				</span>
			{/snippet}

			<svelte:boundary>
				{#snippet pending()}
					<span
						class="flex items-center gap-2 rounded-full border border-base-700 bg-base-850 px-3 py-1 text-xs text-base-400"
					>
						<span class="h-2 w-2 animate-pulse rounded-full bg-base-500"></span>
						checking…
					</span>
				{/snippet}

				{@render badge(healthTone(await getHealth()))}

				{#snippet failed(_error, reset)}
					<button
						type="button"
						onclick={reset}
						class="flex items-center gap-2 rounded-full border border-danger/40 bg-base-850 px-3 py-1 text-xs font-medium text-danger"
					>
						<Icon name="warning-circle" />
						backend offline
					</button>
				{/snippet}
			</svelte:boundary>
		</header>

		<main class="flex-1 overflow-y-auto p-6">
			{@render children()}
		</main>
	</div>
</div>
