import { test, expect } from '@playwright/test';
test.describe('Hosted Vercel smoke', () => {
  test('production loads + save gate bundle live', async ({ page }) => {
    await page.goto('https://adeptui.vercel.app/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await expect(page.locator('body')).toBeVisible({ timeout: 30000 });
    console.log('TITLE:', await page.title());
    // bundle ref
    const html = await page.content();
    const m = html.match(/assets\/index-[A-Za-z0-9_-]+\.js/);
    console.log('BUNDLE:', m ? m[0] : 'none');
    expect(m).toBeTruthy();
  });
});