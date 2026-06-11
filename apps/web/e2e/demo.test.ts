import { expect, test } from '@playwright/test';

test('command center renders the app shell', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByRole('heading', { name: 'Command Center' })).toBeVisible();
});
