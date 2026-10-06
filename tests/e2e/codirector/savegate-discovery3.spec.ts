import { test, expect } from '@playwright/test';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';
test.describe('savegate discovery 3', () => {
  test('direct spatial workspace', async ({ page }) => {
    await page.goto(`/project/${SCHNICK}?workspace=spatial`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(5000);
    console.log('URL:', page.url());
    const panel = page.locator('[data-testid=spatial-map-panel]');
    console.log('panel count:', await panel.count());
    if (await panel.count()) {
      console.log('panel visible:', await panel.isVisible());
      const saveCluster = page.locator('[data-testid=spatial-map-save-cluster]');
      console.log('save cluster count:', await saveCluster.count());
      const saveState = page.locator('[data-testid=spatial-map-save-state]');
      if (await saveState.count()) console.log('save state:', await saveState.innerText());
      const saveBtn = page.locator('[data-testid=spatial-map-save]');
      if (await saveBtn.count()) console.log('save btn:', await saveBtn.innerText());
      const openLib = page.locator('[data-testid=spatial-map-open-library]');
      if (await openLib.count()) console.log('open library:', await openLib.innerText());
    } else {
      const body = await page.locator('body').innerText();
      console.log('BODY:', body.slice(0, 700).replace(/\n+/g, ' | '));
    }
    expect(true).toBeTruthy();
  });
});