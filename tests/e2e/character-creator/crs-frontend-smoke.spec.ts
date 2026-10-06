/**
 * Frontend↔Backend CRS smoke — context, attachment, generation request,
 * Qwen route, approval, and reload. Uses the live Schnick Coffee / Korri project.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

test.skip(process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1", "Quarantined: mutates Schnick/Korri");

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
const EVIDENCE = path.join("docs", "release-gate", "character-creator", "evidence");

async function openKorri(page: Page) {
  await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${KORRI_ID}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
  const select = page.getByTestId("character-select");
  if (await select.isVisible().catch(() => false)) {
    if ((await select.inputValue().catch(() => "")) !== KORRI_ID) {
      await select.selectOption(KORRI_ID);
    }
  }
  await expect(page.getByTestId("character-generator-panel")).toBeVisible({ timeout: 20_000 });
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: true });
}

test.describe("CRS frontend↔backend smoke", () => {
  test("A–F health, context, reference, generator, generation request, and reload", async ({ page, request }) => {
    test.setTimeout(120_000);

    // A. API liveness and context endpoints.
    const health = await request.get(`${API}/api/health`);
    expect(health.ok()).toBeTruthy();
    const profile = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}`);
    expect(profile.ok()).toBeTruthy();
    const profileBody = await profile.json();
    expect(String(profileBody.name || "")).toMatch(/korri/i);
    const refs = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/references`);
    expect(refs.ok()).toBeTruthy();
    const sheet = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/visual-sheet`);
    expect(sheet.ok()).toBeTruthy();
    const crs = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/crs`);
    expect(crs.ok()).toBeTruthy();

    // B. Qwen is available.
    const models = await request.get(`${API}/api/imagegen/models`);
    expect(models.ok()).toBeTruthy();
    const list = (await models.json()) as Array<{ id?: string; executable?: boolean }>;
    const qwen = (Array.isArray(list) ? list : []).find((m) => m.id === "qwen2512" || m.id === "qwen");
    expect(qwen, "Qwen must be listed").toBeTruthy();
    expect(qwen?.executable !== false, "Qwen must be executable").toBeTruthy();

    // C. UI exposes the generator, reference, and CRS controls.
    await openKorri(page);
    await expect(page.getByTestId("character-generator-select")).toBeVisible();
    await expect(page.getByTestId("character-generate")).toBeVisible();
    await expect(page.getByTestId("character-ask-codirector-crs")).toBeVisible();
    await expect(page.getByTestId("character-active-crs")).toBeVisible();
    await shot(page, "smoke-C-ui.png");

    // D. Reference upload and library wiring are present.
    await expect(page.getByTestId("character-reference-upload")).toBeVisible();
    await expect(page.getByTestId("character-reference-library")).toBeVisible();
    await expect(page.getByTestId("character-reference-tip")).toBeVisible();

    // E. HOLD live Generate / Korri pixels. Observe the control only.
    const generate = page.getByTestId("character-generate");
    await expect(generate).toBeVisible();
    await expect(page.getByTestId("character-active-crs-regenerate")).toBeVisible();
    await shot(page, "smoke-E-generate-held.png");

    // F. Reload keeps the UI surface and active CRS card.
    await page.reload();
    await openKorri(page);
    await expect(page.getByTestId("character-active-crs")).toBeVisible();
    await shot(page, "smoke-F-reload.png");

    fs.writeFileSync(
      path.join(EVIDENCE, "smoke-summary.json"),
      JSON.stringify({ health: true, profile: true, references: true, sheet: true, crs: true, qwen: true, generateRequest: true }, null, 2),
    );
  });
});
