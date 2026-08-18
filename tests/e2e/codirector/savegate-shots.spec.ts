import { test, expect } from '@playwright/test';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';
test.describe('Save Gate screenshots', () => {
  test('capture unsaved + saved states', async ({ page }) => {
    await page.goto(`/project/${SCHNICK}?workspace=spatial`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
    await page.waitForTimeout(4000);
    await page.screenshot({ path: 'tests/e2e/screenshots/spatial-map/savegate-unsaved.png', fullPage: false });
    const saveCluster = page.locator('[data-testid=spatial-map-save-cluster]');
    await saveCluster.scrollIntoViewIfNeeded();
    await page.screenshot({ path: 'tests/e2e/screenshots/spatial-map/savegate-cluster-unsaved.png' });
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'tests/e2e/screenshots/spatial-map/savegate-cluster-saved.png' });
  });
  test('capture ERS section clean', async ({ page }) => {
    await page.goto(`/project/${SCHNICK}?workspace=spatial`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
    await page.waitForTimeout(4000);
    const ersSel = page.locator('[data-testid=ers-generator-select]');
    await ersSel.scrollIntoViewIfNeeded();
    await page.screenshot({ path: 'tests/e2e/screenshots/spatial-map/savegate-ers-clean.png' });
  });
});