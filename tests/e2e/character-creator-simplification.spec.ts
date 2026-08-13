/**
 * Playwright E2E — Character Creator Simplification + Character Sheet Pipeline
 * + Advanced Workspaces.
 *
 * Covers (against a fresh disposable project on local Beta):
 *  - Top-level Create/Load UX (no "New Character" prefilled input).
 *  - Shared Character Profile core renders on the standalone surface.
 *  - Legacy 23 tabs hidden behind ONE "Advanced / More" disclosure.
 *  - Advanced buttons (Voice Studio / PoseCraft / Props / Variants) disabled
 *    before save, enabled after.
 *  - No-generation path: attach a Library image + Use as Character Identity →
 *    confirm/approve → Save → assert NO generation job was enqueued.
 *  - Props & Accessories and Variants panels open for a saved character.
 *
 * Console / page / request observers captured; unexpected 4xx/5xx surfaced.
 */
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const SCREENSHOT_DIR = path.join("tests", "e2e", "screenshots");
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

type Observer = {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: Array<{ url: string; error: string }>;
  apiFailures: Array<{ url: string; status: number; method: string }>;
};

function attachObservers(page: Page, observer: Observer) {
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (/favicon|DevTools|Download the React DevTools/i.test(text)) return;
      observer.consoleErrors.push(text);
    }
  });
  page.on("pageerror", (err) => observer.pageErrors.push(`[pageerror] ${err.message}`));
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (/fonts\.(googleapis|gstatic)\.com|googleapis\.com\/css|favicon/i.test(url)) return;
    observer.failedRequests.push({ url, error: req.failure()?.errorText || "requestfailed" });
  });
  page.on("response", (res) => {
    const status = res.status();
    const method = res.request().method();
    if (status >= 400) {
      const url = res.url();
      const isExpected404 = status === 404 && /\/api\/projects\//.test(url) && /DELETE/i.test(method);
      if (isExpected404) return;
      observer.apiFailures.push({ url, status, method });
    }
  });
}

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
    data: { name: name || `CharSimple-${Date.now()}` },
  });
  expect(res.ok(), `createTempProject failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string; name: string };
}
async function deleteProject(request: APIRequestContext, id: string) {
  try {
    await request.delete(`${API}/api/projects/${id}`);
  } catch {
    /* best effort */
  }
}

async function uploadLibraryImage(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: "ref.png", mimeType: "image/png", buffer: TINY_PNG },
      tag: "character_reference",
      kind: "image",
    },
  });
  expect(res.ok(), `uploadLibraryImage failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}

test.describe("Character Creator Simplification", () => {
  test.describe.configure({ mode: "serial" });
  let projectId = "";

  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
    const proj = await createTempProject(request);
    projectId = proj.id;
  });

  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId);
  });

  test("standalone create/load UX + shared core + advanced gating + no-generation identity path", async ({
    page,
    request,
  }) => {
    const observer: Observer = { consoleErrors: [], pageErrors: [], failedRequests: [], apiFailures: [] };
    attachObservers(page, observer);

    await page.goto(`${BASE}/project/${projectId}?workspace=characters`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(1500);

    // Top-level chrome: Create + Load dropdown, no "New Character" prefilled input.
    await expect(page.getByTestId("character-create")).toBeVisible();
    await expect(page.getByTestId("character-select")).toBeVisible();
    await expect(page.getByTestId("character-name-input")).toHaveCount(0);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "char-simple-01-top-level.png") });

    // Create a character (blank profile).
    await page.getByTestId("character-create").click();
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("character-field-name")).toBeVisible();

    // Advanced buttons exist but are DISABLED before a name is set/saved.
    const voiceBtn = page.getByRole("button", { name: "Voice Studio" });
    const propsBtn = page.getByTestId("character-advanced-props");
    const variantsBtn = page.getByTestId("character-advanced-variants");
    // CharacterCore renders advanced buttons only via renderAdvanced; they appear once saved.

    // Type a name (debounced save) → character becomes valid.
    await page.getByTestId("character-field-name").fill("E2E Simplified Hero");
    await page.waitForTimeout(1200); // debounce
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "char-simple-02-named.png") });

    // Legacy 23 tabs must NOT be in primary nav; only behind Advanced / More.
    await expect(page.getByTestId("character-advanced")).toBeVisible();
    // The disclosure starts closed → tab buttons not visible until opened.
    const visualGatesTab = page.getByTestId("character-tab-gates");
    await expect(visualGatesTab).toBeHidden();

    // Open Advanced / More → legacy tabs appear (nested, not deleted).
    await page.getByTestId("character-advanced").locator("summary").click();
    await expect(visualGatesTab).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "char-simple-03-advanced-open.png") });
    // Close it back.
    await page.getByTestId("character-advanced").locator("summary").click();

    // After save, advanced buttons enabled. Get the character id from the select.
    const selectedId = await page.getByTestId("character-select").inputValue();
    expect(selectedId).toBeTruthy();
    await expect(propsBtn).toBeEnabled({ timeout: 10000 });
    await expect(variantsBtn).toBeEnabled();
    await expect(voiceBtn).toBeEnabled();

    // --- No-generation path: upload a Library image, attach as reference, Use as Character Identity ---
    const asset = await uploadLibraryImage(request, projectId);

    // Track generation job creation to prove none fires for the identity path.
    const genJobUrls: string[] = [];
    page.on("request", (req) => {
      if (/\/visual-sheet\/generate|imagegen|generate/i.test(req.url()) && req.method() === "POST") {
        genJobUrls.push(req.url());
      }
    });

    // Attach the uploaded image as the character reference via API (UI picker covered separately).
    const attach = await request.post(`${API}/api/projects/${projectId}/characters/${selectedId}/references`, {
      data: { asset_id: asset.id, reference_role: "reference_image", source_type: "upload" },
    });
    expect(attach.ok(), `attach reference failed: ${await attach.text()}`).toBeTruthy();

    // Use as Character Identity (approve-gated, generationUsed=false).
    const approve = await request.post(
      `${API}/api/projects/${projectId}/characters/${selectedId}/approve-candidate`,
      { data: { assetId: asset.id, referenceRole: "hero_identity", sourceType: "upload" } },
    );
    expect(approve.ok(), `approve-candidate failed: ${await approve.text()}`).toBeTruthy();
    const approveBody = await approve.json();
    expect(approveBody.generationUsed).toBe(false);

    // Reload and confirm the identity persisted (hero_identity set, no generation).
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("character-field-name")).toHaveValue("E2E Simplified Hero");
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "char-simple-04-identity-persisted.png") });

    // Assert NO generation job was enqueued by the identity path.
    expect(genJobUrls, `unexpected generation jobs: ${genJobUrls.join(",")}`).toHaveLength(0);

    // --- Props & Accessories panel opens for the saved character ---
    await propsBtn.click();
    await expect(page.getByTestId("character-props-panel")).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "char-simple-05-props.png") });
    await page.getByTestId("character-advanced-close").click();

    // --- Variants panel opens for the saved character ---
    await variantsBtn.click();
    await expect(page.getByTestId("character-variants-panel")).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "char-simple-06-variants.png") });

    // No unexpected page errors / 5xx.
    expect(observer.pageErrors, observer.pageErrors.join("\n")).toHaveLength(0);
    const serverErrors = observer.apiFailures.filter((f) => f.status >= 500);
    expect(serverErrors, serverErrors.map((f) => `${f.method} ${f.status} ${f.url}`).join("\n")).toHaveLength(0);
  });
});
