import { test, expect } from '@playwright/test';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';
test.describe('savegate discovery 5 - ERS state', () => {
  test('check ERS monitor + use in scene creator', async ({ page }) => {
    await page.goto(`/project/${SCHNICK}?workspace=spatial`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
    await page.waitForTimeout(6000);
    const monitor = page.locator('[data-testid=ers-generation-monitor]');
    console.log('monitor count:', await monitor.count());
    if (await monitor.count()) {
      const phase = await monitor.getAttribute('data-phase');
      console.log('phase:', phase);
      const useSC = page.locator('[data-testid=use-in-scene-creator]');
      console.log('use-in-sc count:', await useSC.count());
      if (await useSC.count()) {
        console.log('use-in-sc text:', (await useSC.innerText()).trim());
        console.log('use-in-sc disabled:', await useSC.isDisabled());
      }
    }
    // Character slots for edit tests
    const charSlots = page.locator('[data-testid^=character-slot-]');
    console.log('character slots:', await charSlots.count());
    for (let i = 0; i < Math.min(await charSlots.count(), 5); i++) {
      const c = charSlots.nth(i);
      console.log('slot', i, 'testid:', await c.getAttribute('data-testid'));
    }
    expect(true).toBeTruthy();
  });
});