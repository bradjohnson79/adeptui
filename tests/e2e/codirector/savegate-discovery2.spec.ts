import { test, expect } from '@playwright/test';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';
test.describe('savegate discovery 2', () => {
  test('find spatial map entry', async ({ page }) => {
    await page.goto(`/project/${SCHNICK}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(3000);
    // Click the Co-Director content area / look for nav buttons
    const buttons = page.locator('button, [role=tab], a');
    const texts = [];
    for (let i = 0; i < Math.min(await buttons.count(), 60); i++) {
      const t = (await buttons.nth(i).innerText().catch(() => '')).trim();
      const tid = await buttons.nth(i).getAttribute('data-testid').catch(() => '');
      if (t || tid) texts.push(`${tid || ''} = ${t.slice(0, 40)}`);
    }
    console.log('CONTROLS:', texts.join(' || '));
    expect(true).toBeTruthy();
  });
});