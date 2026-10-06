/**
 * SenseNova U1.5 Character Creator — Lab project only.
 * Never Schnick Coffee. Never mutate Korri.
 * UI clicks for Generate / Reject / Approve. Live generate only when Ready.
 * Not Ready must skip the live generate — never silent-pass as certified.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const LAB = "SenseNova Integration Lab";
const EVIDENCE = path.resolve(__dirname, "..", "..", "..", "docs", "release-gate", "sensenova-u15", "evidence");
const FORBIDDEN = "2347bf46-3762-4763-86c5-4a6032522278";

test.setTimeout(40 * 60 * 1000);

async function ensureLabProject(request: APIRequestContext): Promise<string> {
  const listed = await request.get(`${API}/api/projects`);
  expect(listed.ok()).toBeTruthy();
  const body = await listed.json();
  const rows = Array.isArray(body) ? body : body.projects || body.items || [];
  const existing = rows.find((row: { name?: string; id?: string }) => String(row.name || "") === LAB);
  if (existing?.id) {
    expect(String(existing.id)).not.toBe(FORBIDDEN);
    return String(existing.id);
  }
  const created = await request.post(`${API}/api/projects`, { data: { name: LAB } });
  expect(created.ok(), await created.text()).toBeTruthy();
  const proj = await created.json();
  const id = String(proj.id || proj.projectId);
  expect(id).not.toBe(FORBIDDEN);
  return id;
}

async function ensureLabCharacter(request: APIRequestContext, projectId: string): Promise<string> {
  const listed = await request.get(`${API}/api/projects/${projectId}/characters`);
  const body = listed.ok() ? await listed.json() : [];
  const rows = Array.isArray(body) ? body : body.characters || body.items || [];
  const existing = rows.find((row: { name?: string }) => /Mira Vale/i.test(String(row.name || "")));
  if (existing?.id) return String(existing.id);
  const created = await request.post(`${API}/api/projects/${projectId}/characters`, {
    data: {
      name: "Mira Vale",
      description: "Disposable Lab cartographer. Not Korri.",
      visual_description:
        "Adult woman, short copper hair, amber eyes, olive field coat, brass compass pendant, warm brown skin.",
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const char = await created.json();
  return String(char.id || char.characterId);
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: true });
}

async function waitForNativeDraft(request: APIRequestContext, projectId: string, characterId: string) {
  let sheetAssetId = "";
  await expect
    .poll(
      async () => {
        const res = await request.get(`${API}/api/projects/${projectId}/characters/${characterId}/visual-sheet`);
        if (!res.ok()) return "";
        const body = await res.json();
        const pack = body.pack || body;
        const cand = (pack.candidates || [])[0] || {};
        const layout = String(cand.layout || cand.sheetLayout || "");
        const jobs = cand.viewJobs || [];
        const nativeDone =
          /native_production_crs/i.test(layout) &&
          jobs.length === 1 &&
          String(jobs[0]?.status || "").toLowerCase() === "done";
        sheetAssetId = nativeDone ? String(cand.sheetAssetId || cand.assetId || "") : "";
        return sheetAssetId;
      },
      { timeout: 35 * 60 * 1000 },
    )
    .not.toEqual("");
  return sheetAssetId;
}

test.describe("SenseNova Character Creator", () => {
  test("lists SenseNova without flipping Flux default", async ({ page, request }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    const projectId = await ensureLabProject(request);
    const characterId = await ensureLabCharacter(request, projectId);
    await page.goto(`${UI}/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    const panel = page.getByTestId("character-generator-panel");
    await expect(panel).toBeVisible({ timeout: 45_000 });
    const select = page.getByTestId("character-generator-select");
    await expect(select).toBeVisible();
    await expect(select.locator('option[value="sensenova"]')).toHaveCount(1, { timeout: 45_000 });
    const options = await select.locator("option").allTextContents();
    expect(options.some((label) => /SenseNova U1\.5/i.test(label))).toBeTruthy();
    expect(options.some((label) => /FLUX/i.test(label))).toBeTruthy();
    // A prior Lab session may have persisted SenseNova. Product default is Flux.
    if ((await select.inputValue()) === "sensenova") {
      await select.selectOption("flux");
    }
    const current = await select.inputValue();
    expect(current).not.toBe("sensenova");
    expect(current).toBe("flux");
    await select.selectOption("sensenova");
    await expect(select).toHaveValue("sensenova");
    await shot(page, "cc-sensenova-selected.png");
    const unexpected = errors.filter((line) => !/favicon|ResizeObserver|net::ERR/i.test(line));
    expect(unexpected, unexpected.join("\n")).toEqual([]);
  });

  test("live native CRS generate only when Ready", async ({ page, request }) => {
    const projectId = await ensureLabProject(request);
    const characterId = await ensureLabCharacter(request, projectId);
    await page.goto(`${UI}/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    const select = page.getByTestId("character-generator-select");
    await expect(select).toBeVisible({ timeout: 45_000 });
    await expect(select.locator('option[value="sensenova"]')).toHaveCount(1, { timeout: 45_000 });
    await select.selectOption("sensenova");
    const selectedLabel = await select.locator("option:checked").textContent();
    const notReadyHint = page.getByTestId("character-local-not-ready");
    const blocked = /Not Ready/i.test(selectedLabel || "") || (await notReadyHint.isVisible().catch(() => false));
    if (blocked) {
      await shot(page, "cc-sensenova-not-ready.png");
      test.skip(true, "SenseNova U1.5 Not Ready — live native CRS blocked");
    }
    const generate = page.getByTestId("character-generate");
    await expect(generate).toBeEnabled();
    await generate.click();
    await shot(page, "cc-sensenova-generating.png");
    const sheetId = await waitForNativeDraft(request, projectId, characterId);
    expect(sheetId).toBeTruthy();
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("character-active-crs-status")).toContainText(/Draft/i, { timeout: 30_000 });
    await shot(page, "cc-sensenova-native-crs-draft.png");
  });
});
