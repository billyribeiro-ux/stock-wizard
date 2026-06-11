/// <reference types="@testing-library/svelte" />

// Mocks for browser APIs not implemented in jsdom but used by the app shell.
Object.defineProperty(window, 'matchMedia', {
	writable: true,
	enumerable: true,
	value: (query: string) => ({
		media: query,
		matches: false,
		onchange: null,
		addEventListener: () => {},
		removeEventListener: () => {},
		addListener: () => {},
		removeListener: () => {},
		dispatchEvent: () => false
	})
});
