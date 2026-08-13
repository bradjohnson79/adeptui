/**
 * Playwright E2E — Library checkbox + bulk delete certification.
 *
 * Runs against https://adeptui.vercel.app/ and captures the exact screenshots
 * required for the active deployed Co-Director Library certification.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "https://adeptui.vercel.app";
const API = process.env.STUDIO_API_BASE || "https://api-beta.adeptui.org";
const SCREENSHOT_DIR = path.join("tests", "e2e", "screenshots");

const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function waitForAppReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 15000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 120_000 },
    )
    .toBeTruthy();
}

async function createTempProject(request: APIRequestContext, name?: string) {
  const res = await request.post(`${API}/api/projects`, {
    data: { name: name || `LibCert-${Date.now()}` },
  });
  expect(res.ok(), `createTempProject failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string; name: string };
}

async function deleteProject(request: APIRequestContext, id: string) {
  try { await request.delete(`${API}/api/projects/${id}`); } catch { /* best effort */ }
}

async function uploadImageAsset(request: APIRequestContext, projectId: string, opts: { name: string; tag?: string }) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: opts.name, mimeType: "image/png", buffer: TINY_PNG },
      tag: opts.tag || opts.name,
      kind: "image",
    },
  });
  expect(res.ok(), `uploadImageAsset failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}

async function listLibrary(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}/library`);
  expect(res.ok(), `listLibrary failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { items?: { id: string; kind: string }[] };
}

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) {
      await page.waitForTimeout(300);
      continue;
    }
    const nameInput = region.getByRole("textbox", { name: /What should I call you/i }).first();
    if (await nameInput.isVisible().catch(() => false)) {
      const current = await nameInput.inputValue().catch(() => "");
      if (!current) await nameInput.fill("Tester");
    }
    for (const label of [/Save and continue/i, /Skip for now/i]) {
      const btn = region.getByRole("button", { name: label }).first();
      if (await btn.isVisible().catch(() => false)) {
        const disabled = await btn.isDisabled().catch(() => false);
        if (!disabled) {
          await btn.click({ force: true }).catch(() => undefined);
          await page.waitForTimeout(800);
          break;
        }
      }
    }
    if (!(await region.isVisible().catch(() => false))) break;
  }
}

async function cancelInFlightGeneration(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const stopBtn = page.getByRole("button", { name: /Stop generating/i }).first();
    if (!(await stopBtn.isVisible().catch(() => false))) return;
    await stopBtn.click({ force: true }).catch(() => undefined);
    await page.waitForTimeout(800);
  }
}

async function clickTabAndWait(page: Page, tabId: string, panelTestIds: string[]) {
  await dismissOnboarding(page);
  await cancelInFlightGeneration(page);
  const tab = page.getByTestId(`codirector-content-tab-${tabId}`);
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    for (const testId of panelTestIds) {
      if (await page.getByTestId(testId).first().isVisible().catch(() => false)) return;
    }
    await cancelInFlightGeneration(page);
    await page.waitForTimeout(1000);
  }
  await expect(page.getByTestId(panelTestIds[0]).first()).toBeVisible({ timeout: 45_000 });
}

async function openCoDirector(page: Page, projectId: string) {
  await page.goto(`${BASE}/co-director?projectId=${encodeURIComponent(projectId)}`);
  await expect(
    page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
  ).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
}

async function screenshot(page: Page, name: string) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const file = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

test.describe("Library checkbox + bulk delete certification", () => {
  let projectId: string;
  let img1: { id: string };
  let img2: { id: string };
  let img3: { id: string };

  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `LibCheckbox-${Date.now()}`);
    projectId = project.id;
    [img1, img2, img3] = await Promise.all([
      uploadImageAsset(request, projectId, { name: "lib-1.png", tag: "LC 1" }),
      uploadImageAsset(request, projectId, { name: "lib-2.png", tag: "LC 2" }),
      uploadImageAsset(request, projectId, { name: "lib-3.png", tag: "LC 3" }),
    ]);
  });

  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId);
  });

  test("certifies Select mode, checkboxes, bulk delete, and persistence", async ({ page, request }) => {
    test.setTimeout(240_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirector(page, projectId);
    await dismissOnboarding(page);
    await cancelInFlightGeneration(page);

    // Open Library tab.
    await clickTabAndWait(page, "library", ["codirector-content-library", "library-media-grid"]);
    const grid = page.getByTestId("library-media-grid");
    await expect(grid).toBeVisible({ timeout: 15_000 });

    const imageCards = grid.locator('[data-testid="library-card-image"]');
    await expect(imageCards.first()).toBeVisible({ timeout: 20_000 });
    await expect.poll(async () => imageCards.count(), { timeout: 15_000 }).toBe(3);

    // 1. Screenshot: Select mode with checkboxes.
    const enterSelectBtn = page.getByTestId("library-enter-select");
    await expect(enterSelectBtn).toBeVisible({ timeout: 5000 });
    await enterSelectBtn.click();
    await expect(page.getByTestId("library-select-all")).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("library-delete-selected")).toBeVisible({ timeout: 5000 });
    await screenshot(page, "library-cert-01-select-mode-checkboxes");

    // 2. Screenshot: 3 selected.
    await imageCards.nth(0).click();
    await page.waitForTimeout(200);
    await imageCards.nth(1).click();
    await page.waitForTimeout(200);
    await imageCards.nth(2).click();
    await page.waitForTimeout(200);

    const deleteSelectedBtn = page.getByTestId("library-delete-selected");
    await expect(deleteSelectedBtn).toBeEnabled({ timeout: 5000 });
    await expect(deleteSelectedBtn).toContainText(/Delete Selected \(3\)/, { timeout: 5000 });
    await screenshot(page, "library-cert-02-three-selected");

    // 3. Screenshot: delete confirmation dialog.
    await deleteSelectedBtn.click();
    const confirmDialog = page.getByRole("alertdialog", { name: /Delete 3 images\?/i });
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });
    await screenshot(page, "library-cert-03-delete-confirmation");

    // 4. Cancel → assets remain.
    await page.getByTestId("library-bulk-delete-cancel").click();
    await expect(confirmDialog).not.toBeVisible({ timeout: 5000 });
    const libAfterCancel = await listLibrary(request, projectId);
    const imageIdsAfterCancel = new Set((libAfterCancel.items || []).filter((a) => a.kind === "image").map((a) => a.id));
    expect(imageIdsAfterCancel.has(img1.id)).toBe(true);
    expect(imageIdsAfterCancel.has(img2.id)).toBe(true);
    expect(imageIdsAfterCancel.has(img3.id)).toBe(true);
    await screenshot(page, "library-cert-04-after-cancel-three-remain");

    // 5. Confirm deletion → assets disappear.
    // Re-enter select mode (Done was clicked implicitly by cancel? No, Done is separate; cancel closes dialog).
    // Cancel closed dialog but select mode remains active; selection is preserved.
    await deleteSelectedBtn.click();
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });
    await page.getByTestId("library-bulk-delete-confirm").click();
    await expect(confirmDialog).not.toBeVisible({ timeout: 5000 });
    await expect.poll(async () => imageCards.count(), { timeout: 15_000 }).toBe(0);
    await screenshot(page, "library-cert-05-post-delete");

    // 6. Reload → deletion persists.
    await page.reload();
    await page.waitForLoadState("networkidle");
    await dismissOnboarding(page);
    await clickTabAndWait(page, "library", ["codirector-content-library", "library-media-grid"]);
    await expect.poll(async () => imageCards.count(), { timeout: 15_000 }).toBe(0);
    const libAfterReload = await listLibrary(request, projectId);
    const imageIdsAfterReload = new Set((libAfterReload.items || []).filter((a) => a.kind === "image").map((a) => a.id));
    expect(imageIdsAfterReload.has(img1.id)).toBe(false);
    expect(imageIdsAfterReload.has(img2.id)).toBe(false);
    expect(imageIdsAfterReload.has(img3.id)).toBe(false);
    await screenshot(page, "library-cert-06-post-delete-reload");
  });
});
