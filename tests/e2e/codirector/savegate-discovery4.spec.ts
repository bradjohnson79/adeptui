import { test, expect } from '@playwright/test';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';
test.describe('savegate discovery 4', () => {
  test('direct spatial workspace long wait', async ({ page }) => {
    await page.goto(`/project/${SCHNICK}?workspace=spatial`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
    console.log('PANEL VISIBLE');
    const saveCluster = page.locator('[data-testid=spatial-map-save-cluster]');
    console.log('save cluster:', await saveCluster.count());
    const saveState = page.locator('[data-testid=spatial-map-save-state]');
    if (await saveState.count()) console.log('save state:', await saveState.innerText());
    const saveBtn = page.locator('[data-testid=spatial-map-save]');
    if (await saveBtn.count()) console.log('save btn:', (await saveBtn.innerText()).trim());
    const openLib = page.locator('[data-testid=spatial-map-open-library]');
    if (await openLib.count()) console.log('open library:', (await openLib.innerText()).trim());
    const useSC = page.locator('[data-testid=use-in-scene-creator]');
    console.log('use-in-sc-creator count:', await useSC.count());
    if (await useSC.count()) console.log('use-in-sc disabled:', await useSC.isDisabled());
    // ERS section
    const ersSel = page.locator('[data-testid=ers-generator-select]');
    console.log('ers selector:', await ersSel.count());
    const ersReason = page.locator('[data-testid=ers-generator-reason]');
    console.log('ers reason count:', await ersReason.count());
    if (await ersReason.count()) console.log('ers reason text:', (await ersReason.innerText()).slice(0, 120));
    // options text
    const opts = page.locator('[data-testid=ers-generator-select] option');
    const optTexts = [];
    for (let i = 0; i < await opts.count(); i++) optTexts.push((await opts.nth(i).innerText()).trim());
    console.log('ERS options:', JSON.stringify(optTexts));
    expect(true).toBeTruthy();
  });
});