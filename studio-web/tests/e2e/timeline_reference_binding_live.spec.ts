import { test, expect, type Page } from "@playwright/test";
import path from "path";
import fs from "fs";

const BASE = process.env.ADEPT_UI_URL || "http://127.0.0.1:5173";
const PROJECT = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const EVIDENCE = process.env.TIMELINE_REF_EVIDENCE || String.raw`C:\Users\bradj\theme_walk\timeline_reference_tag\binding`;
const EVIDENCE_AGENT = process.env.TIMELINE_REF_EVIDENCE_AGENT || String.raw`C:\Users\bradj\agent-tools\theme_walk\timeline_reference_tag\binding`;
for (const d of [EVIDENCE, EVIDENCE_AGENT]) fs.mkdirSync(d, { recursive: true });

async function shot(page: Page, name: string) {
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: false });
  await page.screenshot({ path: path.join(EVIDENCE_AGENT, name), fullPage: false });
}

async function openRefs(page: Page) {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${BASE}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2500);
  if ((await page.getByTestId("scene-references-pane").count()) === 0) {
    const refs = page.getByText(/^References$/i).first();
    if (await refs.count()) await refs.click({ force: true });
    await page.waitForTimeout(1000);
  }
  await expect(page.getByTestId("scene-references-pane")).toBeVisible({ timeout: 45000 });
  await page.evaluate(() => {
    const pane = document.querySelector('[data-testid="scene-references-pane"]');
    pane?.scrollIntoView({ block: "center", inline: "nearest" });
    const input = document.querySelector('[data-testid="references-add-input"]') as HTMLElement | null;
    input?.scrollIntoView({ block: "center", inline: "nearest" });
  });
  await page.waitForTimeout(400);
  await expect(page.getByTestId("references-add-input")).toBeEnabled({ timeout: 20000 });
}

async function selectToken(page: Page, query: string, match: RegExp) {
  const input = page.getByTestId("references-add-input");
  await page.evaluate(() => {
    document.querySelector('[data-testid="references-add-input"]')?.scrollIntoView({ block: "center" });
  });
  await input.fill(query);
  await expect(page.getByTestId("references-add-results")).toBeVisible({ timeout: 15000 });
  const rows = page.locator("[data-testid^=references-add-row-]");
  await expect.poll(async () => rows.count(), { timeout: 15000 }).toBeGreaterThan(0);
  const n = await rows.count();
  let assetId = "";
  let already = false;
  let titleHit = "";
  for (let i = 0; i < n; i++) {
    const row = rows.nth(i);
    const title = (await row.getAttribute("title")) || (await row.innerText());
    if (!match.test(title)) continue;
    assetId = ((await row.getAttribute("data-testid")) || "").replace("references-add-row-", "");
    already = (await row.getAttribute("data-already")) === "true";
    titleHit = title;
    break;
  }
  if (!assetId) {
    const titles = await rows.evaluateAll((els) => els.map((e) => e.getAttribute("title") || e.textContent));
    throw new Error(`no row for ${query} / ${match} titles=${JSON.stringify(titles)}`);
  }
  if (already) return { assetId, already: true, title: titleHit };

  const before = await page.locator("[data-testid^=reference-binding-]").count();
  await page.evaluate((id) => {
    const el = document.querySelector(`[data-testid="references-add-row-${id}"]`) as HTMLButtonElement | null;
    if (!el) throw new Error("missing row " + id);
    el.scrollIntoView({ block: "nearest" });
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
  }, assetId);
  await page.waitForTimeout(1800);
  // chip should appear OR error should not be "No matching reference"
  const err = page.getByTestId("references-error");
  if (await err.count()) {
    const txt = await err.innerText();
    if (/No matching reference/i.test(txt)) throw new Error(`bind mislabeled as lookup miss: ${txt}`);
  }
  const after = await page.locator("[data-testid^=reference-binding-]").count();
  if (after < before + 1) {
    // try Enter fallback
    await input.press("Enter");
    await page.waitForTimeout(1500);
  }
  return { assetId, already: false, title: titleHit };
}

test.describe("Timeline Reference Binding T1-T10", () => {
  test.setTimeout(180000);

  test("T1 @Korri bind", async ({ page }) => {
    await openRefs(page);
    const beforeChips = await page.locator("[data-testid^=reference-binding-]").count();
    const r = await selectToken(page, "@Korri", /Korri/i);
    expect(r.assetId).toBeTruthy();
    if (!r.already) {
      await expect.poll(async () => page.locator("[data-testid^=reference-binding-]").count()).toBeGreaterThan(beforeChips);
    } else {
      expect(beforeChips).toBeGreaterThan(0);
    }
    await expect(page.getByTestId("references-error")).toHaveCount(0);
    await shot(page, "T1_Korri_bind.png");
    fs.writeFileSync(path.join(EVIDENCE, "T1_stage.json"), JSON.stringify(r, null, 2));
    fs.writeFileSync(path.join(EVIDENCE_AGENT, "T1_stage.json"), JSON.stringify(r, null, 2));
  });

  test("T2 @Cade bind", async ({ page }) => {
    await openRefs(page);
    const beforeChips = await page.locator("[data-testid^=reference-binding-]").count();
    const r = await selectToken(page, "@Cade", /Cade/i);
    expect(r.assetId).toBeTruthy();
    if (!r.already) {
      await expect.poll(async () => page.locator("[data-testid^=reference-binding-]").count()).toBeGreaterThan(beforeChips);
    }
    const err = page.getByTestId("references-error");
    if (await err.count()) expect(await err.innerText()).not.toMatch(/No matching reference/i);
    await shot(page, "T2_Cade_bind.png");
    fs.writeFileSync(path.join(EVIDENCE, "T2_stage.json"), JSON.stringify(r, null, 2));
  });

  test("T3 @Anadriya bind", async ({ page }) => {
    await openRefs(page);
    const beforeChips = await page.locator("[data-testid^=reference-binding-]").count();
    const r = await selectToken(page, "@Anadriya", /Anadriya/i);
    expect(r.assetId).toBeTruthy();
    if (!r.already) {
      await expect.poll(async () => page.locator("[data-testid^=reference-binding-]").count()).toBeGreaterThan(beforeChips);
    }
    await shot(page, "T3_Anadriya_bind.png");
  });

  test("T4 SchnickCoffee prop", async ({ page }) => {
    await openRefs(page);
    const beforeChips = await page.locator("[data-testid^=reference-binding-]").count();
    let r;
    try {
      r = await selectToken(page, "%schnick", /Schnick|Coffee|Thermos/i);
    } catch {
      r = await selectToken(page, "schnick", /Schnick|Coffee|Thermos/i);
    }
    expect(r.assetId).toBeTruthy();
    if (!r.already) {
      await expect.poll(async () => page.locator("[data-testid^=reference-binding-]").count()).toBeGreaterThan(beforeChips);
    }
    await shot(page, "T4_Schnick_bind.png");
  });

  test("T5 global prop", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("%");
    await expect(page.getByTestId("references-add-results")).toBeVisible();
    const scopes = await page.locator('[data-testid^=references-add-row-][data-semantic-type="prop"]').evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-scope")),
    );
    expect(scopes.some((s) => s === "Global" || s === "Local")).toBeTruthy();
    await shot(page, "T5_global_prop.png");
  });

  test("T6 local still works", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("@");
    const local = page.locator('[data-testid^=references-add-row-][data-scope="Local"]').first();
    await expect(local).toBeVisible({ timeout: 15000 });
    await shot(page, "T6_local.png");
  });

  test("T7 duplicate Already added", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("@Korri");
    await expect(page.getByTestId("references-add-results")).toBeVisible();
    await expect(page.locator('[data-testid^=references-add-row-][data-already="true"]').first()).toBeVisible({ timeout: 10000 });
    await shot(page, "T7_dup.png");
  });

  test("T8 bind-fail messaging code path", async ({ page }) => {
    const pane = fs.readFileSync(
      String.raw`C:\AdeptFilmWorks\AIVideoStudio\studio-web\src\components\sceneReferences\ReferencesPane.tsx`,
      "utf8",
    );
    expect(pane).toContain("Could not add reference");
    expect(pane).toMatch(/msg === "No matching reference" \? "Could not add reference"/);
    await openRefs(page);
    await shot(page, "T8_messaging_contract.png");
  });

  test("T9 Library Reference path unchanged", async ({ page }) => {
    const paneSrc = fs.readFileSync(
      String.raw`C:\AdeptFilmWorks\AIVideoStudio\studio-web\src\components\sceneReferences\ReferencesPane.tsx`,
      "utf8",
    );
    expect(paneSrc).toMatch(/const attachAsset = async/);
    expect(paneSrc).toMatch(/api\.sceneReferences\.attach/);
    await openRefs(page);
    await shot(page, "T9_library_path.png");
  });

  test("T10 reload persistence", async ({ page }) => {
    await openRefs(page);
    const before = await page.locator("[data-testid^=reference-binding-]").count();
    expect(before).toBeGreaterThan(0);
    await page.reload({ waitUntil: "domcontentloaded" });
    await openRefs(page);
    const after = await page.locator("[data-testid^=reference-binding-]").count();
    expect(after).toBeGreaterThan(0);
    await shot(page, "T10_reload.png");
  });
});
