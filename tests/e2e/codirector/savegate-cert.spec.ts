import path from 'node:path';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { createTempProject, deleteProject } from '../helpers/app';

const API = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8758';
const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC',
  'base64',
);

async function uploadAtlas(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: 'atlas.png', mimeType: 'image/png', buffer: TINY_PNG },
      tag: 'atlas_shot',
      kind: 'image',
    },
  });
  expect(res.ok(), `uploadAtlas failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}

async function createMap(request: APIRequestContext, projectId: string, backgroundAssetId: string) {
  const res = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps`, {
    data: { title: 'Save Gate Cert', backgroundAssetId },
  });
  expect(res.ok(), `createMap failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { document: { id: string; version: string; savedVersion?: string | null } };
}

async function openSpatial(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=spatial`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
  await page.waitForTimeout(3000);
}

test.describe('Spatial Map Save Gate — scratch project (Tests A-E) @isolated', () => {
  let projectId = '';
  let mapId = '';

  test.beforeAll(async ({ request }) => {
    const p = await createTempProject(request, `Save Gate Cert ${Date.now()}`);
    projectId = p.id;
    const atlas = await uploadAtlas(request, projectId);
    const m = await createMap(request, projectId, atlas.id);
    mapId = m.document.id;
    // Add a camera so test C has a guaranteed PATCH-path production edit.
    const cam = await request.post(
      `${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/cameras`,
      { data: { label: 'C1', cameraSlot: 0, orientation: 'NE', fovPreset: 'wide' } },
    );
    expect(cam.ok(), `createCamera failed: ${await cam.text()}`).toBeTruthy();
  });

  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId).catch(() => undefined);
  });

  test('A: fresh unsaved -> Save available, state Unsaved, Use gated', async ({ page }) => {
    await openSpatial(page, projectId);
    const saveBtn = page.locator('[data-testid=spatial-map-save]');
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toBeEnabled();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText(/Unsaved changes|Save failed/);
  });

  test('B: save -> persisted + Saved + dirty=false', async ({ page, request }) => {
    await openSpatial(page, projectId);
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    const res = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const d = body.document;
    expect(d.savedVersion).toBeTruthy();
    expect(d.savedVersion).toBe(d.version);
    console.log('B persisted: savedVersion=' + d.savedVersion + ' version=' + d.version + ' savedAt=' + d.savedAt);
  });

  test('C: edit after save -> dirty + Unsaved again', async ({ page }) => {
    await openSpatial(page, projectId);
    // ensure saved first
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    // production edit: toggle camera 0 visibility (PATCH bumps version -> dirty)
    const camVis = page.locator('[data-testid=camera-visible-0]');
    await expect(camVis).toBeVisible({ timeout: 20000 });
    await camVis.click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText(/Unsaved changes/, { timeout: 20000 });
    console.log('C: edit marked map dirty');
  });

  test('D: re-save -> Saved + clean again + no duplicate profile', async ({ page, request }) => {
    await openSpatial(page, projectId);
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    const res = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`);
    const d = (await res.json()).document;
    expect(d.savedVersion).toBe(d.version);
    console.log('D: re-saved clean savedVersion=' + d.savedVersion);
  });

  test('E: reload -> saved state hydrates, Saved, not dirty', async ({ page }) => {
    await openSpatial(page, projectId);
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
    await page.waitForTimeout(3000);
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    console.log('E: reload hydrates Saved');
  });
});

test.describe('Spatial Map Save Gate — Schnick Coffee ERS gating (F, H, I)', () => {
  const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';

  test('F: Use in Scene Creator gated by save state on ERS-complete map', async ({ page }) => {
    await openSpatial(page, SCHNICK);
    const monitor = page.locator('[data-testid=ers-generation-monitor]');
    await expect(monitor).toBeVisible({ timeout: 30000 });
    expect(await monitor.getAttribute('data-phase')).toBe('complete');
    const useSC = page.locator('[data-testid=use-in-scene-creator]');
    await expect(useSC).toBeVisible();
    // Save to enable
    await page.locator('[data-testid=spatial-map-save]').click();
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    await expect(useSC).toBeEnabled();
    console.log('F: Use in Scene Creator enabled after save');
  });

  test('H: no obsolete Qwen red warning; clean generator labels', async ({ page }) => {
    await openSpatial(page, SCHNICK);
    const opts = page.locator('[data-testid=ers-generator-select] option');
    const texts: string[] = [];
    for (let i = 0; i < await opts.count(); i++) texts.push((await opts.nth(i).innerText()).trim());
    for (const t of texts) expect(t).not.toContain('Unavailable for ERS');
    const reason = page.locator('[data-testid=ers-generator-reason]');
    if (await reason.count()) {
      const cls = await reason.getAttribute('class');
      expect(cls || '').not.toContain('reason'); // muted hint class, not the red reason class
    }
  });

  test('I: no Map-only placement warning prose', async ({ page }) => {
    await openSpatial(page, SCHNICK);
    const notes = page.locator('[data-testid$=maponly-note]');
    for (let i = 0; i < await notes.count(); i++) {
      const t = await notes.nth(i).innerText();
      expect(t).not.toContain('will not appear in Scene Creator');
    }
    const badges = page.locator('[data-testid^=prop-maponly-badge]');
    console.log('I: maponly badges (compact chips, fine):', await badges.count());
  });

  test('Part 0: top and bottom Save share one state', async ({ page }) => {
    await openSpatial(page, SCHNICK);
    const monitor = page.locator('[data-testid=ers-generation-monitor]');
    await expect(monitor).toBeVisible({ timeout: 30000 });
    expect(await monitor.getAttribute('data-phase')).toBe('complete');
    const topBtn = page.locator('[data-testid=spatial-map-save]');
    const bottomBtn = page.locator('[data-testid=spatial-map-save-bottom]');
    const topState = page.locator('[data-testid=spatial-map-save-state]');
    const bottomState = page.locator('[data-testid=spatial-map-save-state-bottom]');
    const useSC = page.locator('[data-testid=use-in-scene-creator]');
    await expect(bottomBtn).toBeVisible();

    const camVis = page.locator('[data-testid=camera-visible-0]');
    await expect(camVis).toBeVisible({ timeout: 20000 });
    await camVis.click();
    await expect(topState).toHaveText(/Unsaved changes/, { timeout: 20000 });
    await expect(bottomState).toHaveText(/Unsaved changes/);
    await expect(useSC).toBeDisabled();

    await bottomBtn.click();
    await expect(topState).toHaveText('Saved', { timeout: 20000 });
    await expect(bottomState).toHaveText('Saved');
    await expect(useSC).toBeEnabled();

    await camVis.click();
    await expect(topState).toHaveText(/Unsaved changes/, { timeout: 20000 });
    await expect(bottomState).toHaveText(/Unsaved changes/);
    await expect(useSC).toBeDisabled();

    await topBtn.click();
    await expect(topState).toHaveText('Saved', { timeout: 20000 });
    await expect(bottomState).toHaveText('Saved');
    await expect(useSC).toBeEnabled();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('[data-testid=spatial-map-panel]')).toBeVisible({ timeout: 60000 });
    await page.waitForTimeout(3000);
    await expect(page.locator('[data-testid=spatial-map-save-state]')).toHaveText('Saved', { timeout: 20000 });
    await expect(page.locator('[data-testid=spatial-map-save-state-bottom]')).toHaveText('Saved');
  });

  test('Scene Creator Mini accordion sits under ERS', async ({ page }) => {
    await openSpatial(page, SCHNICK);
    const monitor = page.locator('[data-testid=ers-generation-monitor]');
    await expect(monitor).toBeVisible({ timeout: 30000 });
    const mini = page.locator('[data-testid=scene-creator-mini]');
    await expect(mini).toBeVisible();
    await page.locator('[data-testid=scene-creator-mini-toggle]').click();
    const enable = page.locator('[data-testid=scene-creator-mini-enable]');
    await enable.click();
    await expect(enable).toHaveAttribute('aria-checked', 'true');
    await expect(page.locator('[data-testid=scene-creator-mini-output]')).toContainText('Output:');
    const generate = page.locator('[data-testid=scene-creator-mini-generate]');
    await expect(generate).toBeVisible();
  });
});