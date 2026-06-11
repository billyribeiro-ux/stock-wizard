/**
 * Icon safelist.
 *
 * The `<Icon>` component builds its class via interpolation
 * (`icon-[ph--{name}]`), which Tailwind's static scanner cannot see. Listing
 * every Phosphor icon we use here as a complete literal token ensures the
 * Tailwind v4 + `@iconify/tailwind4` pipeline generates the corresponding CSS
 * rule at build time. Keep this in sync with the `name` props used across the app.
 *
 * This module has no runtime effect; it exists purely so the class strings are
 * present in source for the build-time scan.
 */
export const ICON_SAFELIST = [
	'icon-[ph--gauge]',
	'icon-[ph--scan]',
	'icon-[ph--table]',
	'icon-[ph--gear-six]',
	'icon-[ph--chart-line]',
	'icon-[ph--pulse]',
	'icon-[ph--heartbeat]',
	'icon-[ph--broadcast]',
	'icon-[ph--lightning]',
	'icon-[ph--warning]',
	'icon-[ph--warning-circle]',
	'icon-[ph--check-circle]',
	'icon-[ph--x-circle]',
	'icon-[ph--x]',
	'icon-[ph--circle]',
	'icon-[ph--database]',
	'icon-[ph--stack]',
	'icon-[ph--clock]',
	'icon-[ph--clock-countdown]',
	'icon-[ph--arrow-up]',
	'icon-[ph--arrow-down]',
	'icon-[ph--arrow-right]',
	'icon-[ph--arrows-down-up]',
	'icon-[ph--caret-up]',
	'icon-[ph--caret-down]',
	'icon-[ph--caret-right]',
	'icon-[ph--trend-up]',
	'icon-[ph--trend-down]',
	'icon-[ph--minus]',
	'icon-[ph--plus]',
	'icon-[ph--play]',
	'icon-[ph--target]',
	'icon-[ph--crosshair]',
	'icon-[ph--shield-check]',
	'icon-[ph--scales]',
	'icon-[ph--thumbs-up]',
	'icon-[ph--thumbs-down]',
	'icon-[ph--clock-clockwise]',
	'icon-[ph--key]',
	'icon-[ph--plug]',
	'icon-[ph--plugs-connected]',
	'icon-[ph--trash]',
	'icon-[ph--floppy-disk]',
	'icon-[ph--spinner-gap]',
	'icon-[ph--magnifying-glass]',
	'icon-[ph--list-bullets]',
	'icon-[ph--info]',
	'icon-[ph--flag]',
	'icon-[ph--chart-bar]',
	'icon-[ph--chart-scatter]',
	'icon-[ph--brain]',
	'icon-[ph--eye]',
	'icon-[ph--terminal-window]',
	'icon-[ph--sliders-horizontal]',
	'icon-[ph--clipboard-text]'
] as const;
