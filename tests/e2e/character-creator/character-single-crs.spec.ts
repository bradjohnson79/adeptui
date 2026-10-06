/**
 * Playwright A–O — Character Creator single canonical CRS on live Beta.
 * A–D use Korri for visual proof. E–O use a disposable Schnick Coffee character.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

test.skip(process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1", "Quarantined: writes Schnick Coffee");

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
const EVIDENCE = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  "docs",
  "release-gate",
  "character-creator",
  "evidence",
);

test.setTimeout(20 * 60 * 1000);

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
  const name = `CRS Single ${Date.now()}`;
  const res = await request.post(`${API}/api/projects/${PROJECT_ID}/characters`, {
    data: {
      name,
      description: "Disposable Character Creator single-CRS certification fixture with a usable appearance brief.",
      visual_description: "Adult woman, dark hair, warm skin, practical jacket, cinematic anime.",
    },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return { id: String(body.id || body.characterId), name };
}

test.describe("Character Creator single CRS A–O", () => {
  test("A–D selector, Qwen default, no candidate grid", async ({ page, request }) => {
    await expect.poll(async () => (await request.get(`${API}/api/health`)).ok(), { timeout: 60_000 }).toBeTruthy();
    await openCharacter(page, KORRI_ID);
    await expect(page.getByTestId("character-generator-select")).toBeVisible();
    const select = page.getByTestId("character-generator-select");
    const optionValues = await select.locator("option").evaluateAll((els) =>
      els.map((el) => (el as HTMLOptionElement).value),
    );
    const options = await select.locator("option").allTextContents();
    expect(optionValues[0]).toBe("qwen_edit_2509");
    expect(options.some((t) => /qwen image edit 2509/i.test(t))).toBeTruthy();
    expect(options.some((t) => /gpt image 2/i.test(t))).toBeTruthy();
    expect(optionValues).not.toContain("sd15");
    const value = await select.inputValue();
    expect(["qwen_edit_2509", "qwen2512", "qwen", "flux", "illustrious", "gpt-image-2", "zimage"]).toContain(value);
    await expect(page.getByTestId("character-previous-generations")).toHaveCount(0);
    await expect(page.getByTestId("character-candidate-grid")).toHaveCount(0);
    await expect(page.getByTestId("character-more-generators")).toHaveCount(0);
    await expect(page.getByTestId("character-active-crs")).toBeVisible();
    await expect(page.getByTestId("character-save")).toBeVisible();
    await expect(page.getByTestId("character-reset")).toBeVisible();
    await shot(page, "single-crs-A-D-korri.png");
    for (const width of [1920, 1440, 1024, 768] as const) {
      await page.setViewportSize({ width, height: 900 });
      await shot(page, `single-crs-responsive-${width}.png`);
    }
  });

  test("E–O disposable generate, preview, regenerate, approve, persist, GPT Image 2", async ({ page, request }) => {
    test.skip(process.env.ADEPT_ALLOW_LIVE_GENERATE !== "1", "HOLD live Generate / Korri pixels — sanitation phase 1");
    test.skip(process.env.ADEPT_ALLOW_SCHNICK_WRITE !== "1", "HOLD Schnick writes — disposable test project only");
    test.setTimeout(70 * 60 * 1000);
    test.skip(!process.env.ADEPT_BETA_TARGET, "Live Beta generate required");
    const created = await createDisposable(request);
    await openCharacter(page, created.id);
    await expect(page.getByTestId("character-generate")).toBeEnabled({ timeout: 20_000 });
    const before = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`);
    await page.getByTestId("character-generate").click();
    await expect(page.getByTestId("generation-progress")).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(
        async () => {
          const packRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`);
          if (!packRes.ok()) return "wait";
          const pack = (await packRes.json()) as {
            pack?: { candidates?: Array<{ sheetAssetId?: string; assetId?: string }>; candidateCount?: number; status?: string };
            candidates?: Array<{ sheetAssetId?: string; assetId?: string }>;
            status?: string;
          };
          const body = pack.pack || pack;
          const candidates = body.candidates || [];
          const asset = String(candidates[0]?.sheetAssetId || candidates[0]?.assetId || "").trim();
          const count = Number(body.candidateCount || candidates.length || 0);
          const status = String(body.status || pack.status || "").toUpperCase();
          if (status === "FAILED") return "failed";
          if (count !== 1) return `count:${count}`;
          return asset ? "ready" : "generating";
        },
        { timeout: 20 * 60 * 1000 },
      )
      .toBe("ready");
    void before;
    const firstPack = await (
      await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`)
    ).json();
    const firstBody = (firstPack.pack || firstPack) as { candidates?: Array<{ sheetAssetId?: string }> };
    const firstAsset = String(firstBody.candidates?.[0]?.sheetAssetId || "").trim();
    expect(firstAsset.length).toBeGreaterThan(8);
    await expect(page.getByTestId("generation-progress")).toHaveCount(0, { timeout: 60_000 });
    await expect(page.getByTestId("character-candidate-grid")).toHaveCount(0);
    const preview = page.getByTestId("character-active-crs-preview");
    if (await preview.isVisible().catch(() => false)) {
      await preview.click();
      await shot(page, "single-crs-G-preview.png");
      await page.keyboard.press("Escape");
    }
    await page.getByTestId("character-active-crs-regenerate").click();
    await expect
      .poll(
        async () => {
          const packRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`);
          const pack = (await packRes.json()) as {
            pack?: { candidates?: Array<{ sheetAssetId?: string }>; candidateCount?: number };
            candidates?: Array<{ sheetAssetId?: string }>;
          };
          const body = pack.pack || pack;
          const asset = String((body.candidates || [])[0]?.sheetAssetId || "").trim();
          const count = Number(body.candidateCount || 1);
          const status = String(body.status || pack.status || "").toUpperCase();
          if (status === "FAILED") return "failed";
          if (count !== 1) return `count:${count}`;
          return asset && asset !== firstAsset ? "ready" : "generating";
        },
        { timeout: 20 * 60 * 1000 },
      )
      .toBe("ready");
    const approve = page.getByTestId("character-active-crs-approve");
    await expect(approve).toBeEnabled({ timeout: 60_000 });
    await approve.click();
    await expect(page.getByTestId("character-approved-banner")).toContainText(`@${created.name}`, { timeout: 30_000 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-candidate-grid")).toHaveCount(0);
    await expect(page.getByTestId("character-approved-banner")).toContainText(`@${created.name}`);
    const approvedPack = await (
      await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`)
    ).json();
    const approvedAsset = String(((approvedPack.pack || approvedPack).candidates || [])[0]?.sheetAssetId || "").trim();
    await page.getByTestId("character-generator-select").selectOption("gpt-image-2");
    await shot(page, "single-crs-N-gpt.png");
    const gptOption = page.getByTestId("character-generator-select").locator('option[value="gpt-image-2"]');
    const gptDisabled = await gptOption.isDisabled().catch(() => false);
    if (!gptDisabled) {
      await page.getByTestId("character-generate").click();
      await expect
        .poll(
          async () => {
            const packRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`);
            if (!packRes.ok()) return "wait";
            const pack = (await packRes.json()) as {
              pack?: { candidates?: Array<{ sheetAssetId?: string }>; candidateCount?: number };
              candidates?: Array<{ sheetAssetId?: string }>;
            };
            const body = pack.pack || pack;
            const asset = String((body.candidates || [])[0]?.sheetAssetId || "").trim();
            const count = Number(body.candidateCount || (body.candidates || []).length || 0);
            if (count !== 1) return `count:${count}`;
            return asset && asset !== approvedAsset ? "ready" : "generating";
          },
          { timeout: 20 * 60 * 1000 },
        )
        .toBe("ready");
      await shot(page, "single-crs-O-gpt-result.png");
    }
    await request.delete(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}`).catch(() => undefined);
  });

  test("E–O continue approve persist GPT on existing disposable", async ({ page, request }) => {
    test.skip(process.env.ADEPT_ALLOW_LIVE_GENERATE !== "1", "HOLD live Generate / Korri pixels — sanitation phase 1");
    const continueId = process.env.ADEPT_CRS_CONTINUE_CHARACTER_ID || "";
    test.skip(!continueId, "No in-flight disposable to continue");
    test.setTimeout(40 * 60 * 1000);
    const profileRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${continueId}`);
    expect(profileRes.ok()).toBeTruthy();
    const profile = (await profileRes.json()) as { name?: string };
    const name = String(profile.name || "");
    await openCharacter(page, continueId);
    await expect
      .poll(
        async () => {
          const packRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${continueId}/visual-sheet`);
          if (!packRes.ok()) return "wait";
          const pack = (await packRes.json()) as {
            pack?: { candidates?: Array<{ sheetAssetId?: string }>; status?: string; candidateCount?: number };
            candidates?: Array<{ sheetAssetId?: string }>;
            status?: string;
          };
          const body = pack.pack || pack;
          if (String(body.status || "").toUpperCase() === "FAILED") return "failed";
          const asset = String((body.candidates || [])[0]?.sheetAssetId || "").trim();
          return asset ? "ready" : "generating";
        },
        { timeout: 20 * 60 * 1000 },
      )
      .toBe("ready");
    const preview = page.getByTestId("character-active-crs-preview");
    if (await preview.isVisible().catch(() => false)) {
      await preview.click();
      await shot(page, "single-crs-G-preview.png");
      await page.keyboard.press("Escape");
    }
    const approve = page.getByTestId("character-active-crs-approve");
    if (await approve.isVisible().catch(() => false)) {
      await expect(approve).toBeEnabled({ timeout: 60_000 });
      page.once("dialog", (dialog) => dialog.accept());
      await approve.click();
    }
    await expect(page.getByTestId("character-approved-banner")).toContainText(`@${name}`, { timeout: 30_000 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-candidate-grid")).toHaveCount(0);
    await expect(page.getByTestId("character-approved-banner")).toContainText(`@${name}`);
    const approvedPack = await (
      await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${continueId}/visual-sheet`)
    ).json();
    const approvedAsset = String(((approvedPack.pack || approvedPack).candidates || [])[0]?.sheetAssetId || "").trim();
    await page.getByTestId("character-generator-select").selectOption("gpt-image-2");
    await shot(page, "single-crs-N-gpt.png");
    const gptOption = page.getByTestId("character-generator-select").locator('option[value="gpt-image-2"]');
    const gptDisabled = await gptOption.isDisabled().catch(() => false);
    if (!gptDisabled) {
      await page.getByTestId("character-generate").click();
      await expect
        .poll(
          async () => {
            const packRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${continueId}/visual-sheet`);
            if (!packRes.ok()) return "wait";
            const pack = (await packRes.json()) as {
              pack?: { candidates?: Array<{ sheetAssetId?: string }>; candidateCount?: number; status?: string };
              candidates?: Array<{ sheetAssetId?: string }>;
              status?: string;
            };
            const body = pack.pack || pack;
            if (String(body.status || "").toUpperCase() === "FAILED") return "failed";
            const asset = String((body.candidates || [])[0]?.sheetAssetId || "").trim();
            const count = Number(body.candidateCount || (body.candidates || []).length || 0);
            if (count !== 1) return `count:${count}`;
            return asset && asset !== approvedAsset ? "ready" : "generating";
          },
          { timeout: 20 * 60 * 1000 },
        )
        .toBe("ready");
      await shot(page, "single-crs-O-gpt-result.png");
    }
  });
});
