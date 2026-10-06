import { test, expect } from '@playwright/test';
test('smoke', async ({ page }) => {
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  expect(await page.title()).toBeTruthy();
  console.log('TITLE:', await page.title());
});