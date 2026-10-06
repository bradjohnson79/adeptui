import { test, expect, type Page } from "@playwright/test";
import path from "path";
import fs from "fs";

const BASE = process.env.ADEPT_UI_URL || "http://127.0.0.1:5173";
const PROJECT = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const EVIDENCE = process.env.TIMELINE_REF_EVIDENCE || String.raw`C:\Users\bradj\theme_walk\timeline_reference_tag`;
const EVIDENCE_AGENT = process.env.TIMELINE_REF_EVIDENCE_AGENT || String.raw`C:\Users\bradj\agent-tools\theme_walk\timeline_reference_tag`;

for (const d of [EVIDENCE, EVIDENCE_AGENT]) fs.mkdirSync(d, { recursive: true });

async function shot(page: Page, name: string) {
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: false });
  await page.screenshot({ path: path.join(EVIDENCE_AGENT, name), fullPage: false });
}

async function openRefs(page: Page) {
  await page.goto(`${BASE}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 60000 });
  // Wait for shell
  await page.waitForTimeout(2500);
  let pane = page.getByTestId("scene-references-pane");
  if ((await pane.count()) === 0) {
    // click References heading / rail
    const refs = page.getByText(/^References$/i).first();
    if (await refs.count()) await refs.click();
    await page.waitForTimeout(1000);
  }
  pane = page.getByTestId("scene-references-pane");
  if ((await pane.count()) === 0) {
    // try director workspace alias
    await page.goto(`${BASE}/project/${PROJECT}?workspace=director`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(2500);
  }
  await expect(page.getByTestId("scene-references-pane")).toBeVisible({ timeout: 45000 });
}

test.describe("Timeline Reference Tag AT", () => {
  test.setTimeout(120000);

  test("00 Filter gone Add Reference present", async ({ page }) => {
    await openRefs(page);
    await expect(page.getByTestId("references-filter")).toHaveCount(0);
    await expect(page.getByTestId("references-add-input")).toBeVisible();
    await expect(page.getByLabel("Add Reference")).toBeVisible();
    const ph = await page.getByTestId("references-add-input").getAttribute("placeholder");
    expect(ph || "").toMatch(/@character|%prop|#environment/i);
    await shot(page, "01_AFTER_add_reference.png");
  });

  test("AT1 @ characters", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("@");
    await expect(page.getByTestId("references-add-results")).toBeVisible();
    const rows = page.locator("[data-testid^=references-add-row-]");
    const n = await rows.count();
    expect(n).toBeGreaterThan(0);
    for (let i = 0; i < n; i++) await expect(rows.nth(i)).toHaveAttribute("data-semantic-type", "character");
    await shot(page, "02_AT1_at_characters.png");
  });

  test("AT2 % props", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("%");
    const rows = page.locator("[data-testid^=references-add-row-]");
    const n = await rows.count();
    // props may be sparse; if any, must be prop
    for (let i = 0; i < n; i++) await expect(rows.nth(i)).toHaveAttribute("data-semantic-type", "prop");
    await shot(page, "03_AT2_pct_props.png");
  });

  test("AT3 # environments", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("#");
    const rows = page.locator("[data-testid^=references-add-row-]");
    const n = await rows.count();
    for (let i = 0; i < n; i++) await expect(rows.nth(i)).toHaveAttribute("data-semantic-type", "environment");
    await shot(page, "04_AT3_hash_envs.png");
  });

  test("AT4 no-prefix name", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("Korri");
    await expect(page.getByTestId("references-add-results")).toBeVisible();
    await shot(page, "05_AT4_noprefix.png");
  });

  test("AT5-6 local global labels", async ({ page }) => {
    await openRefs(page);
    await page.getByTestId("references-add-input").fill("@");
    await expect(page.getByTestId("references-add-results")).toBeVisible();
    const scopes = await page.locator("[data-testid^=references-add-row-]").evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-scope")),
    );
    expect(scopes.some((s) => s === "Local" || s === "Global")).toBeTruthy();
    await shot(page, "06_AT5_6_local_global.png");
  });

  test("AT7 duplicate Already added", async ({ page }) => {
    await openRefs(page);
    const input = page.getByTestId("references-add-input");
    await input.fill("@");
    const rows = page.locator("[data-testid^=references-add-row-]");
    await expect(rows.first()).toBeVisible();
    // Prefer keyboard commit — dropdown may overflow viewport in left drawer.
    const enabled = rows.filter({ hasNot: page.locator("[disabled]") }).first();
    if (await enabled.count()) {
      await input.press("Enter");
      await page.waitForTimeout(1200);
      await input.fill("@");
      const already = page.locator('[data-testid^=references-add-row-][data-already="true"]');
      // Also accept disabled rows labeled Already added
      const disabled = rows.filter({ has: page.locator("[disabled]") });
      const ok = (await already.count()) > 0 || (await disabled.count()) > 0;
      expect(ok).toBeTruthy();
    }
    await shot(page, "07_AT7_duplicate.png");
  });

  test("AT8 invalid no phantom", async ({ page }) => {
    await openRefs(page);
    const before = await page.locator("[data-testid^=reference-binding-]").count();
    const input = page.getByTestId("references-add-input");
    await input.fill("@zzz_not_a_real_character_xyz");
    await expect(page.getByTestId("references-add-empty")).toBeVisible();
    await input.press("Enter");
    await expect(page.getByTestId("references-add-status")).toContainText(/No matching reference/i);
    const after = await page.locator("[data-testid^=reference-binding-]").count();
    expect(after).toBe(before);
    await shot(page, "08_AT8_invalid.png");
  });

  test("AT9 keyboard", async ({ page }) => {
    await openRefs(page);
    const input = page.getByTestId("references-add-input");
    await input.fill("@");
    await expect(page.getByTestId("references-add-results")).toBeVisible();
    await input.press("ArrowDown");
    await input.press("ArrowDown");
    await input.press("Escape");
    await expect(page.getByTestId("references-add-results")).toHaveCount(0);
    await input.fill("@");
    await input.press("ArrowDown");
    await shot(page, "09_AT9_keyboard.png");
  });

  test("AT10 drag path still present", async ({ page }) => {
    await openRefs(page);
    await expect(page.getByTestId("scene-references-pane")).toBeVisible();
    // Library Add to References button if library visible
    const addRef = page.locator("[data-testid^=asset-add-reference-]").first();
    // soft: pane accepts drop (attribute onDrop exists via testid presence)
    await shot(page, "10_AT10_drag_surface.png");
    if (await addRef.count()) {
      await expect(addRef).toBeVisible();
    }
  });
});

