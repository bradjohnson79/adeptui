import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

const BETA_UI_BASE = "http://127.0.0.1:5173";
const BETA_API_BASE = "http://127.0.0.1:8758";
const BETA_API_PORT = "8758";

/** Live Beta certification target when ADEPT_BETA_TARGET=1 or equivalent 8760/8758 wiring is set. */
export const BETA_TARGET =
  process.env.ADEPT_BETA_TARGET === "1" ||
  process.env.ADEPT_BETA_TARGET === "true" ||
  process.env.ADEPT_BETA_TARGET === "TRUE" ||
  process.env.PLAYWRIGHT_BASE_URL === BETA_UI_BASE ||
  process.env.STUDIO_API_BASE === BETA_API_BASE ||
  process.env.STUDIO_API_PORT === BETA_API_PORT;

export const API =
  process.env.STUDIO_API_BASE ||
  (BETA_TARGET
    ? BETA_API_BASE
    : `http://127.0.0.1:${process.env.STUDIO_API_PORT || "8742"}`);
export const FIXTURE =
  process.env.ADEPT_PACK_FIXTURE_BASE_URL ||
  `http://127.0.0.1:${process.env.E2E_FIXTURE_PORT || "8765"}`;

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
  // /api/e2e/* is mounted only when STUDIO_E2E=1 (isolated harness). Live Beta
  // intentionally omits those routes — requiring them here made Beta smoke impossible.
  if (!BETA_TARGET) {
    await expect
      .poll(async () => okGet(`${API}/api/e2e/status`), { timeout: 30_000 })
      .toBeTruthy();
  }
}

export async function createTempProject(request: APIRequestContext, name?: string) {
  const res = await request.post(`${API}/api/projects`, {
    data: { name: name || `E2E ${Date.now()}` },
  });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{ id: string; name: string }>;
}

export async function deleteProject(request: APIRequestContext, id: string) {
  try {
    const res = await request.delete(`${API}/api/projects/${id}`);
    return res.ok();
  } catch {
    return false;
  }
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

export async function confirmInstallPreflight(page: Page) {
  const dialog = page.locator(".install-preflight-dialog[role='dialog']").last();
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.getByTestId("install-preflight-confirm").check();
  await expect(dialog.getByTestId("install-preflight-submit")).toBeEnabled({ timeout: 15_000 });
  await dialog.getByTestId("install-preflight-submit").click();
}

export async function setInstallPreflightDestination(page: Page, folder: string) {
  const dialog = page.locator(".install-preflight-dialog[role='dialog']").last();
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.getByTestId("install-preflight-destination").fill(folder);
  await expect(dialog.getByTestId("install-preflight-destination")).toHaveValue(folder);
}

export async function browseForcedFolder(page: Page, folder: string) {
  await setForcedBrowsePath(page, folder);
  const dialog = page
    .locator(".setup-dialog[role='dialog'], .install-preflight-dialog[role='dialog']")
    .last();
  await expect(dialog).toBeVisible({ timeout: 45_000 });
  await dialog.getByRole("button", { name: /Browse for folder/i }).click();
  const selectedPath = dialog.locator(".setup-selected-path code, [role='status'] code").last();
  await expect(selectedPath).toContainText(folder, { timeout: 15_000 });
}

export async function openSetup(
  page: Page,
  projectId: string,
  opts: { dismissDialogs?: boolean; setupMode?: "guided" | "ai_guided" | "manual" } = {},
) {
  const dismissDialogs = opts.dismissDialogs !== false;
  // Pack / Source Manager card flows require the component grid. Default to manual so a
  // persisted localStorage `ai_guided` preference from other suites cannot hide the grid.
  const setupMode = opts.setupMode ?? "manual";
  await page.goto(`/project/${projectId}?workspace=setup&setupMode=${setupMode}`);
  await expect(page.locator(".setup-wizard-page").first()).toBeVisible({ timeout: 45_000 });
  if (dismissDialogs) {
    await dismissSetupDialogs(page);
  }
  if (setupMode === "ai_guided") {
    await expect(page.getByTestId("ai-guided-setup-panel").or(page.locator("#ai-guided-setup-heading")).first()).toBeVisible({
      timeout: 30_000,
    });
    return;
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

export async function clearComponentLocation(request: APIRequestContext, componentId: string) {
  const res = await request.post(`${API}/api/e2e/clear-component-location`, {
    data: { component_id: componentId },
  });
  expect(res.ok()).toBeTruthy();
}

export async function clearActiveInstallJobs(request: APIRequestContext, componentId: string) {
  const res = await request.get(`${API}/api/setup/install-jobs?componentId=${encodeURIComponent(componentId)}`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { jobs?: Array<{ id?: string; active?: boolean }> };
  for (const job of body.jobs || []) {
    if (!job?.id || !job.active) continue;
    const cancel = await request.post(`${API}/api/setup/install-jobs/${job.id}/cancel`);
    // Cancel may race with completion — accept ok or already-terminal.
    if (!cancel.ok()) {
      const text = await cancel.text().catch(() => "");
      if (!/not.?active|terminal|already|404|409/i.test(text)) {
        expect(cancel.ok()).toBeTruthy();
      }
    }
  }
  await expect
    .poll(async () => {
      const status = await request.get(
        `${API}/api/setup/install-jobs?componentId=${encodeURIComponent(componentId)}`,
      );
      if (!status.ok()) return false;
      const payload = (await status.json()) as { jobs?: Array<{ active?: boolean }> };
      return (payload.jobs || []).every((job) => !job.active);
    }, { timeout: 30_000 })
    .toBeTruthy();
}

type InstallJobSummary = {
  id?: string;
  active?: boolean;
  state?: string;
  terminal?: boolean;
};

function isActiveInstallJob(job: InstallJobSummary) {
  const state = String(job.state || "");
  return (
    job.active === true
    || (job.terminal !== true
      && /^(queued|preparing|downloading|installing|configuring|verifying|repairing|cancelling|resuming|restart_required)/i.test(
        state,
      ))
  );
}

/** Cancel every active install job (works on live Beta — no STUDIO_E2E required). */
export async function clearAllActiveInstallJobs(request: APIRequestContext) {
  const listJobs = async () => {
    const res = await request.get(`${API}/api/setup/install-jobs`);
    if (!res.ok()) return null;
    const body = (await res.json()) as { jobs?: InstallJobSummary[] };
    return body.jobs || [];
  };

  const jobs = await listJobs();
  if (!jobs) return;
  for (const job of jobs) {
    if (!job?.id) continue;
    if (!isActiveInstallJob(job)) continue;
    await request.post(`${API}/api/setup/install-jobs/${job.id}/cancel`).catch(() => undefined);
  }
  await expect
    .poll(async () => {
      const nextJobs = await listJobs();
      if (!nextJobs) return false;
      return nextJobs.every((job) => !isActiveInstallJob(job));
    }, { timeout: 45_000 })
    .toBeTruthy();
}

/**
 * Deterministic pre/post test cleanup for live Beta certification (Addendum 9).
 * Uses public Setup APIs on Beta; optionally harness e2e recover when available.
 */
export async function resetLiveBetaTestSurface(
  request: APIRequestContext,
  page?: Page,
) {
  await clearAllActiveInstallJobs(request);
  if (!BETA_TARGET) {
    await request.post(`${API}/api/e2e/recover-operations`).catch(() => undefined);
    await request.post(`${API}/api/e2e/recover-jobs`).catch(() => undefined);
    await request.post(`${API}/api/e2e/clear-pack-overrides`).catch(() => undefined);
  }
  if (page) {
    await page.context().clearCookies().catch(() => undefined);
    await page
      .context()
      .addInitScript(() => {
        try {
          localStorage.clear();
          sessionStorage.clear();
        } catch {
          /* ignore */
        }
      })
      .catch(() => undefined);
    await page
      .evaluate(() => {
        try {
          localStorage.clear();
          sessionStorage.clear();
        } catch {
          /* ignore */
        }
      })
      .catch(() => undefined);
  }
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
