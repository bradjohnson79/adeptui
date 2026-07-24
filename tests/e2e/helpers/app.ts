import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8742";
export const FIXTURE =
  process.env.ADEPT_PACK_FIXTURE_BASE_URL || "http://127.0.0.1:8765";

export async function waitForAppReady(request: APIRequestContext) {
  const okGet = async (url: string) => {
    try {
      const res = await request.get(url);
      return res.ok();
    } catch {
      return false;
    }
  };
  await expect
    .poll(async () => okGet(`${API}/api/health`), { timeout: 120_000 })
    .toBeTruthy();
  await expect
    .poll(async () => okGet(`${API}/api/setup/status`), { timeout: 60_000 })
    .toBeTruthy();
  await expect
    .poll(async () => okGet(`${API}/api/e2e/status`), { timeout: 30_000 })
    .toBeTruthy();
}

export async function createTempProject(request: APIRequestContext, name?: string) {
  const res = await request.post(`${API}/api/projects`, {
    data: { name: name || `E2E ${Date.now()}` },
  });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{ id: string; name: string }>;
}

export async function deleteProject(request: APIRequestContext, id: string) {
  const res = await request.delete(`${API}/api/projects/${id}`);
  return res.ok();
}

export async function dismissSetupDialogs(page: Page) {
  for (let i = 0; i < 4; i += 1) {
    const cancel = page
      .locator(".setup-dialog[role='dialog'] .row-actions button.ghost, [role='dialog'] .row-actions button.ghost")
      .filter({ hasText: /cancel/i })
      .first();
    if (!(await cancel.isVisible().catch(() => false))) break;
    await cancel.click({ force: true });
    await page.waitForTimeout(150);
  }
}

export async function confirmCheckpoint(page: Page) {
  const dialog = page.locator(".setup-dialog[role='dialog']").last();
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.locator(".row-actions button.primary").click();
}

export async function browseForcedFolder(page: Page, folder: string) {
  await setForcedBrowsePath(page, folder);
  const dialog = page.locator(".setup-dialog[role='dialog']").last();
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.getByRole("button", { name: /Browse for folder/i }).click();
  await expect(dialog.locator("code")).toContainText(folder, { timeout: 15_000 });
}

export async function openSetup(
  page: Page,
  projectId: string,
  opts: { dismissDialogs?: boolean } = {},
) {
  const dismissDialogs = opts.dismissDialogs !== false;
  await page.goto(`/project/${projectId}?workspace=setup`);
  await expect(page.locator(".setup-wizard-page").first()).toBeVisible({ timeout: 45_000 });
  if (dismissDialogs) {
    await dismissSetupDialogs(page);
  }
  await expect(page.locator(".setup-component-grid").first()).toBeVisible({ timeout: 30_000 });
}

export async function ensurePackSource(request: APIRequestContext, packId: string) {
  await request.post(`${API}/api/e2e/recover-operations`);
  await request.post(`${API}/api/setup/components/${encodeURIComponent(packId)}/refresh-source`);
  await expect
    .poll(async () => {
      try {
        const status = await request.get(`${API}/api/setup/status`);
        const body = await status.json();
        const comp = body.components.find((c: { id: string }) => c.id === packId);
        return Boolean(comp?.source_available) && comp?.status !== "download_unavailable";
      } catch {
        return false;
      }
    }, { timeout: 60_000 })
    .toBeTruthy();
}

export async function setFixtureScenario(
  request: APIRequestContext,
  scenario: Record<string, unknown>,
) {
  const res = await request.post(`${FIXTURE}/control/scenario`, { data: scenario });
  expect(res.ok()).toBeTruthy();
}

export async function setForcedBrowsePath(page: Page, folder: string) {
  await page.evaluate((p) => {
    (window as Window & { __ADEPT_E2E_FORCED_PATH__?: string }).__ADEPT_E2E_FORCED_PATH__ = p;
  }, folder);
}

export async function clearForcedBrowsePath(page: Page) {
  await page.evaluate(() => {
    delete (window as Window & { __ADEPT_E2E_FORCED_PATH__?: string }).__ADEPT_E2E_FORCED_PATH__;
  });
}

export function makeTempDir(prefix = "adept-e2e-pack-") {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

export async function packSourceOverride(
  request: APIRequestContext,
  packId: string,
  url: string | null,
) {
  const res = await request.post(`${API}/api/e2e/pack-source-override`, {
    data: { pack_id: packId, url },
  });
  expect(res.ok()).toBeTruthy();
}

export async function clearPackOverrides(request: APIRequestContext) {
  await request.post(`${API}/api/e2e/clear-pack-overrides`);
}

export function writeLinkFixture(
  dir: string,
  opts: { packId: string; version?: string; invalidJson?: boolean; omitPackJson?: boolean },
) {
  fs.mkdirSync(dir, { recursive: true });
  if (!opts.omitPackJson) {
    const body = opts.invalidJson
      ? "{not-json"
      : JSON.stringify(
          {
            schemaVersion: 1,
            id: opts.packId,
            name: opts.packId,
            version: opts.version || "1.0.0",
          },
          null,
          2,
        );
    fs.writeFileSync(path.join(dir, "pack.json"), body);
  }
  fs.mkdirSync(path.join(dir, "presets"), { recursive: true });
  fs.writeFileSync(path.join(dir, "presets", "sample.json"), '{"ok":true}');
  return dir;
}

export async function countApiCalls(page: Page, pathIncludes: string, ms: number) {
  let count = 0;
  const handler = (req: { url: () => string }) => {
    if (req.url().includes(pathIncludes)) count += 1;
  };
  page.on("request", handler);
  await page.waitForTimeout(ms);
  page.off("request", handler);
  return count;
}
