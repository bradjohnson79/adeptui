import { expect, test, type Page } from '@playwright/test';

const API = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8758';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';

async function openSpatial(page: Page) {
  await page.goto(`/project/${SCHNICK}?workspace=spatial`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
  await page.waitForTimeout(3000);
}

test.describe('Scene Creator Mini production fidelity — Schnick Coffee', () => {
  test('camera cards expose Shot Size + Primary Subject (shared panel)', async ({ page }) => {
    await openSpatial(page);
    const shotSize = page.locator('[data-testid=camera-shot-size-0]');
    await expect(shotSize).toBeVisible({ timeout: 30000 });
    const primary = page.locator('[data-testid=camera-primary-subject-0]');
    await expect(primary).toBeVisible();
    const options = await shotSize.locator('option').allInnerTexts();
    expect(options).toEqual(expect.arrayContaining(['Auto', 'Wide', 'Medium', 'Medium Close', 'Close Up']));
  });

  test('shot-size edit -> dirty -> Save -> clean (Save Gate regression)', async ({ page }) => {
    await openSpatial(page);
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    const shotSize = page.locator('[data-testid=camera-shot-size-0]');
    await expect(shotSize).toBeVisible({ timeout: 30000 });
    await shotSize.selectOption('medium_close');
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText(/Unsaved changes/, { timeout: 20000 });
    const miniGenerate = page.locator('[data-testid=scene-creator-mini-generate]');
    if (await miniGenerate.isVisible()) await expect(miniGenerate).toBeDisabled();
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
  });

  test('camera reference strip renders C1-C4 rows under ERS', async ({ page }) => {
    await openSpatial(page);
    const strip = page.locator('[data-testid=camera-reference-strip]');
    await expect(strip).toBeVisible({ timeout: 30000 });
    for (const label of ['C1', 'C2', 'C3', 'C4']) {
      await expect(page.locator(`[data-testid=camera-ref-${label}]`)).toBeVisible({ timeout: 15000 });
      await expect(page.locator(`[data-testid=camera-ref-generate-${label}]`)).toBeVisible();
    }
  });

  test('camera reference generate starts a real job (C2)', async ({ page, request }) => {
    test.setTimeout(300_000);
    await openSpatial(page);
    const strip = page.locator('[data-testid=camera-reference-strip]');
    await expect(strip).toBeVisible({ timeout: 30000 });
    const row = page.locator('[data-testid=camera-ref-C2]');
    await expect(row).toBeVisible({ timeout: 15000 });
    const btn = page.locator('[data-testid=camera-ref-generate-C2]');
    // Only run when ERS composite exists so the job can actually execute.
    const res = await request.get(`${API}/api/spatial-map/projects/${SCHNICK}/maps`);
    expect(res.ok()).toBeTruthy();
    await btn.click();
    await expect(btn).toBeDisabled();
    await expect(page.locator('[data-testid=camera-ref-C2] .spatial-map__mini-chip.is-validating, [data-testid=camera-ref-C2] .spatial-map__mini-chip.is-pass, [data-testid=camera-ref-C2] .spatial-map__mini-chip.is-failed')).toBeVisible({ timeout: 30000 });
  });

  test('Mini accordion opens and shows take provenance line', async ({ page }) => {
    await openSpatial(page);
    const mini = page.locator('[data-testid=scene-creator-mini]');
    await expect(mini).toBeVisible({ timeout: 30000 });
    await page.locator('[data-testid=scene-creator-mini-toggle]').click();
    await page.locator('[data-testid=scene-creator-mini-enable]').click();
    await expect(page.locator('[data-testid=scene-creator-mini-output]')).toContainText('Output:');
    const versionLine = page.locator('[data-testid=scene-creator-mini-take-version]');
    if (await versionLine.count()) {
      await expect(versionLine).toContainText('Map v');
    }
  });
});
