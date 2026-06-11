<script lang="ts">
	/**
	 * Phosphor icon wrapper. Renders an Iconify CSS icon as a span using the
	 * iconify/tailwind4 plugin's dynamic class convention. No per-icon Svelte
	 * components are imported, keeping Vite dep-optimization fast.
	 *
	 * Usage: name="chart-line" renders the ph chart-line glyph.
	 */
	interface Props {
		name: string;
		/** extra classes (size, color, etc.) */
		class?: string;
		label?: string;
	}

	let { name, class: className = '', label }: Props = $props();
</script>

<span
	class="icon-[ph--{name}] inline-block shrink-0 {className}"
	role={label ? 'img' : 'presentation'}
	aria-label={label}
	aria-hidden={label ? undefined : 'true'}
></span>
