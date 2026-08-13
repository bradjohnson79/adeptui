/**
 * Playwright E2E — Library all-media selection + sticky toolbar certification.
 *
 * Default: local e2e harness (api http://127.0.0.1:8742, web from Playwright baseURL).
 * For production certification run with:
 *   PLAYWRIGHT_BASE_URL=https://adeptui.vercel.app/ STUDIO_API_BASE=https://api-beta.adeptui.org
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8742";
const SCREENSHOT_DIR = path.join("tests", "e2e", "screenshots");

const FIXTURES = path.join("tests", "e2e", "fixtures", "codirector-prebeta");
const IMAGE = fs.readFileSync(path.join(FIXTURES, "cert-image.png"));
const VIDEO = fs.readFileSync(path.join(FIXTURES, "cert-video.mp4"));
const AUDIO = fs.readFileSync(path.join(FIXTURES, "cert-tone.wav"));
const DOCUMENT = Buffer.from("test document", "utf-8");

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
    data: { name: name || `LibAll-${Date.now()}` },
  });
  expect(res.ok(), `createTempProject failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string; name: string };
}

async function deleteProject(request: APIRequestContext, id: string) {
  try { await request.delete(`${API}/api/projects/${id}`); } catch { /* best effort */ }
}

async function uploadAsset(
  request: APIRequestContext,
  projectId: string,
  opts: { name: string; tag: string; kind: string; mimeType: string; buffer: Buffer },
) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: opts.name, mimeType: opts.mimeType, buffer: opts.buffer },
      tag: opts.tag,
      kind: opts.kind,
    },
    timeout: 60_000,
  });
  expect(res.ok(), `uploadAsset failed (${opts.kind}): ${await res.text()}`).toBeTruthy();
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

async function clickFilter(page: Page, filterId: string) {
  const btn = page.getByTestId(`library-filter-${filterId}`);
  await expect(btn).toBeVisible({ timeout: 5000 });
  await btn.click();
  await page.waitForTimeout(300);
}

async function scrollLibrary(page: Page) {
  const body = page.locator(".codirector-content-body").first();
  await body.evaluate((el) => el.scrollTo({ top: el.scrollHeight, behavior: "instant" }));
  await page.waitForTimeout(500);
}

test.describe("Library all-media selection + sticky toolbar certification", () => {
  let projectId: string;
  let assets: { imageIds: string[]; videoId: string; audioId: string; documentId: string };

  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `LibAllMedia-${Date.now()}`);
    projectId = project.id;

    const images = await Promise.all(
      Array.from({ length: 20 }).map((_, i) =>
        uploadAsset(request, projectId, {
          name: `img-${i}.png`,
          tag: `Img ${i}`,
          kind: "image",
          mimeType: "image/png",
          buffer: IMAGE,
        }),
      ),
    );
    const video = await uploadAsset(request, projectId, {
      name: "clip.mp4",
      tag: "Vid 1",
      kind: "video",
      mimeType: "video/mp4",
      buffer: VIDEO,
    });
    const audio = await uploadAsset(request, projectId, {
      name: "sound.wav",
      tag: "Aud 1",
      kind: "audio",
      mimeType: "audio/wav",
      buffer: AUDIO,
    });
    const document = await uploadAsset(request, projectId, {
      name: "doc.txt",
      tag: "Doc 1",
      kind: "document",
      mimeType: "text/plain",
      buffer: DOCUMENT,
    });

    assets = {
      imageIds: images.map((a) => a.id),
      videoId: video.id,
      audioId: audio.id,
      documentId: document.id,
    };
  });

  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId);
  });

  test("certifies all media selectable, filtered Select All, sticky toolbar, mixed delete, and persistence", async ({ page, request }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirector(page, projectId);
    await dismissOnboarding(page);
    await cancelInFlightGeneration(page);

    // Open Library tab.
    await clickTabAndWait(page, "library", ["codirector-content-library", "library-media-grid"]);
    const grid = page.getByTestId("library-media-grid");
    await expect(grid).toBeVisible({ timeout: 15_000 });
    const allCards = grid.locator('[data-testid^="library-card-"]');
    await expect.poll(async () => allCards.count(), { timeout: 30_000 }).toBe(24);

    const imageCards = grid.locator('[data-testid="library-card-image"]');
    const videoCards = grid.locator('[data-testid="library-card-video"]');
    const audioCards = grid.locator('[data-testid="library-card-audio"]');
    const documentCards = grid.locator('[data-testid="library-card-document"]');
    await expect(imageCards.first()).toBeVisible({ timeout: 20_000 });
    await expect(videoCards.first()).toBeVisible({ timeout: 20_000 });
    await expect(audioCards.first()).toBeVisible({ timeout: 20_000 });
    await expect(documentCards.first()).toBeVisible({ timeout: 20_000 });

    // Enter Select mode.
    const enterSelectBtn = page.getByTestId("library-enter-select");
    await expect(enterSelectBtn).toBeVisible({ timeout: 5000 });
    await enterSelectBtn.click();
    await expect(page.getByTestId("library-select-all")).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("library-delete-selected")).toBeVisible({ timeout: 5000 });

    // Select one of each media type.
    await imageCards.first().click();
    await page.waitForTimeout(200);
    await videoCards.first().click();
    await page.waitForTimeout(200);
    await audioCards.first().click();
    await page.waitForTimeout(200);
    await documentCards.first().click();
    await page.waitForTimeout(200);

    const deleteSelectedBtn = page.getByTestId("library-delete-selected");
    await expect(deleteSelectedBtn).toBeEnabled({ timeout: 5000 });
    await expect(deleteSelectedBtn).toContainText(/Delete Selected \(4\)/, { timeout: 5000 });
    await screenshot(page, "library-all-media-01-mixed-selection");

    // Filter Images → Select All should select only images.
    await clickFilter(page, "images");
    await expect.poll(async () => imageCards.count(), { timeout: 10_000 }).toBe(20);
    await expect(videoCards.count()).toBe(0);
    await expect(audioCards.count()).toBe(0);
    await expect(documentCards.count()).toBe(0);

    await page.getByTestId("library-select-all").click();
    await page.waitForTimeout(300);
    await expect(deleteSelectedBtn).toContainText(/Delete Selected \(20\)/, { timeout: 5000 });
    await page.getByTestId("library-exit-select").click();
    await page.waitForTimeout(300);
    await expect(page.getByTestId("library-enter-select")).toBeVisible({ timeout: 5000 });

    // Filter Video → Select All should select only video.
    await clickFilter(page, "video");
    await expect.poll(async () => videoCards.count(), { timeout: 10_000 }).toBe(1);
    await enterSelectBtn.click();
    await page.getByTestId("library-select-all").click();
    await page.waitForTimeout(300);
    await expect(deleteSelectedBtn).toContainText(/Delete Selected \(1\)/, { timeout: 5000 });
    await page.getByTestId("library-exit-select").click();
    await page.waitForTimeout(300);

    // Filter Audio → Select All should select only audio.
    await clickFilter(page, "audio");
    await expect.poll(async () => audioCards.count(), { timeout: 10_000 }).toBe(1);
    await enterSelectBtn.click();
    await page.getByTestId("library-select-all").click();
    await page.waitForTimeout(300);
    await expect(deleteSelectedBtn).toContainText(/Delete Selected \(1\)/, { timeout: 5000 });
    await page.getByTestId("library-exit-select").click();
    await page.waitForTimeout(300);

    // Filter Documents → Select All should select only document.
    await clickFilter(page, "documents");
    await expect.poll(async () => documentCards.count(), { timeout: 10_000 }).toBe(1);
    await enterSelectBtn.click();
    await page.getByTestId("library-select-all").click();
    await page.waitForTimeout(300);
    await expect(deleteSelectedBtn).toContainText(/Delete Selected \(1\)/, { timeout: 5000 });
    await page.getByTestId("library-exit-select").click();
    await page.waitForTimeout(300);

    // Clear Selection should clear without exiting Select mode.
    await clickFilter(page, "all");
    await enterSelectBtn.click();
    await page.getByTestId("library-select-all").click();
    await page.waitForTimeout(300);
    await expect(deleteSelectedBtn).toContainText(/Delete Selected \(24\)/, { timeout: 5000 });
    await page.getByTestId("library-select-all").click(); // toggles to Clear Selection
    await page.waitForTimeout(300);
    await expect(deleteSelectedBtn).toContainText(/Delete Selected$/, { timeout: 5000 });
    await expect(deleteSelectedBtn).toBeDisabled();

    // Sticky toolbar while scrolling.
    await page.getByTestId("library-select-all").click();
    await page.waitForTimeout(300);
    await scrollLibrary(page);
    await expect(page.getByTestId("library-select-all")).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("library-delete-selected")).toContainText(/Delete Selected \(24\)/, { timeout: 5000 });
    await expect(page.getByTestId("library-filter-all")).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("library-filter-images")).toBeVisible({ timeout: 5000 });
    await screenshot(page, "library-all-media-02-sticky-toolbar-scroll");

    // Cancel delete preserves all assets.
    await deleteSelectedBtn.click();
    const confirmDialog = page.getByRole("alertdialog", { name: /Delete 24 assets\?/i });
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });
    await screenshot(page, "library-all-media-03-delete-confirmation");
    await page.getByTestId("library-bulk-delete-cancel").click();
    await expect(confirmDialog).not.toBeVisible({ timeout: 5000 });

    const libBeforeDelete = await listLibrary(request, projectId);
    const beforeIds = new Set((libBeforeDelete.items || []).map((a) => a.id));
    expect(beforeIds.size).toBe(24);
    expect(beforeIds.has(assets.videoId)).toBe(true);
    expect(beforeIds.has(assets.audioId)).toBe(true);
    expect(beforeIds.has(assets.documentId)).toBe(true);

    // Confirm delete removes all.
    await deleteSelectedBtn.click();
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });
    await page.getByTestId("library-bulk-delete-confirm").click();
    await expect(confirmDialog).not.toBeVisible({ timeout: 5000 });
    await expect.poll(async () => allCards.count(), { timeout: 15_000 }).toBe(0);

    // Reload → deleted assets remain gone.
    await page.reload();
    await page.waitForLoadState("networkidle");
    await dismissOnboarding(page);
    await clickTabAndWait(page, "library", ["codirector-content-library", "library-media-grid"]);
    await expect.poll(async () => allCards.count(), { timeout: 15_000 }).toBe(0);
    const libAfterReload = await listLibrary(request, projectId);
    const afterIds = new Set((libAfterReload.items || []).map((a) => a.id));
    expect(afterIds.size).toBe(0);
    await screenshot(page, "library-all-media-04-post-delete-reload");
  });
});
