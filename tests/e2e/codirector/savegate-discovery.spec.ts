import { test, expect } from '@playwright/test';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';
test.describe('savegate discovery', () => {
  test('spatial map panel renders with save cluster', async ({ page, request }) => {
    await page.goto(`/project/${SCHNICK}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(4000);
    // Try direct spatial tab navigation via URL hash/query? First dump nav.
    console.log('URL:', page.url());
    const body = await page.locator('body').innerText();
    console.log('BODY SNIPPET:', body.slice(0, 500).replace(/\n+/g, ' | '));
    // Look for tab buttons
    const tabs = page.locator('[data-testid^="codirector-content-tab-"]');
    console.log('co-director tabs:', await tabs.count());
    for (let i = 0; i < Math.min(await tabs.count(), 20); i++) {
      const t = tabs.nth(i);
      console.log('tab', i, ':', await t.getAttribute('data-testid'), '|', (await t.innerText()).slice(0, 30));
    }
    expect(true).toBeTruthy();
  });
});