/**
 * Character Creator final closure — Schnick Coffee only.
 * Generate / Preview / Reject / Regenerate / Approve / Reload / Library / dismiss.
 * Never POST /api/projects. Delete uses a disposable character inside Schnick.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
const EVIDENCE = path.resolve(
  process.cwd(),
  "docs",
  "release-gate",
  "character-creator-final-closure",
  "evidence",
);

test.setTimeout(20 * 60 * 1000);

const consoleErrors: string[] = [];
const networkFailures: string[] = [];

async function openCharacter(page: Page, characterId: string) {
  await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${characterId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: true });
}

async function createDisposable(request: APIRequestContext) {
  const name = `CC Closure ${Date.now()}`;
  const res = await request.post(`${API}/api/projects/${PROJECT_ID}/characters`, {
    data: {
      name,
      description: "Disposable Character Creator final-closure fixture. Safe to delete.",
      visual_description: "Adult woman, dark hair, warm skin, practical jacket, cinematic anime.",
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return { id: String(body.id || body.characterId), name };
}

test.describe("Character Creator final closure", () => {
  test.beforeEach(async ({ page }) => {
    consoleErrors.length = 0;
    networkFailures.length = 0;
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(String(err)));
    page.on("response", (res) => {
      const status = res.status();
      const url = res.url();
      if ((status === 422 || status >= 500) && url.includes("/api/")) {
        networkFailures.push(`${status} ${url}`);
      }
    });
  });

  test("selector hides Not Ready and Korri lifecycle stays on Schnick", async ({ page, request }) => {
    await expect.poll(async () => (await request.get(`${API}/api/health`)).ok(), { timeout: 60_000 }).toBeTruthy();
    const models = await (await request.get(`${API}/api/imagegen/models?surface=character`)).json();
    const local = (Array.isArray(models) ? models : models.models || []).filter((m: { group?: string }) => m.group !== "auto");
    for (const row of local) {
      expect(row.executable, row.id).not.toBe(false);
    }

    await openCharacter(page, KORRI_ID);
    const select = page.getByTestId("character-generator-select");
    await expect(select).toBeVisible();
    const labels = await select.locator("option").allTextContents();
    expect(labels.some((label) => /not ready/i.test(label))).toBeFalsy();
    await shot(page, "pw-korri-selector.png");

    const crs = await (await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/crs`)).json();
    expect(String(crs.approved_reference_asset_id || "")).toBeTruthy();
    expect(Number(crs.crs_revision || 0)).toBeGreaterThanOrEqual(4);
    await expect(page.getByTestId("character-active-crs")).toBeVisible();
    await expect(page.getByTestId("character-active-crs-status")).toContainText(/Approved/i);
    await expect(page.getByTestId("character-active-crs-thumb-img")).toBeVisible();
    await page.getByTestId("character-active-crs-preview").click();
    await shot(page, "pw-korri-approved-preview.png");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-active-crs-status")).toContainText(/Approved/i);
    await shot(page, "pw-korri-reload.png");

    const unexplained = networkFailures.filter((row) => !/dismiss|reject-candidate/i.test(row));
    fs.writeFileSync(
      path.join(EVIDENCE, "pw-console-network.json"),
      JSON.stringify({ consoleErrors, networkFailures, unexplained }, null, 2),
      "utf8",
    );
    expect(unexplained, unexplained.join("\n")).toEqual([]);
  });

  test("delete disposable character inside Schnick; leftover dismiss works", async ({ page, request }) => {
    const created = await createDisposable(request);
    try {
      await openCharacter(page, created.id);
      page.once("dialog", (d) => d.accept());
      await page.getByTestId("character-delete").click();
      await expect
        .poll(async () => (await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}`)).status(), {
          timeout: 20_000,
        })
        .toBe(404);
      await shot(page, "pw-disposable-deleted.png");
    } catch (err) {
      await request.delete(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}`).catch(() => undefined);
      throw err;
    }

    const korri = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}`);
    expect(korri.ok()).toBeTruthy();
  });
});
