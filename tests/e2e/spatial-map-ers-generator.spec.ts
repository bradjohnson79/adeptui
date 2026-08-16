/**
 * Spatial Map ERS generator selector — observe-only.
 * Default is Qwen. Changing to GPT Image 2 must not POST.
 * HOLD: do not click Generate / Retry / Regenerate.
 */
import { expect, test, type Page } from "@playwright/test";
import { openCoDirectorFullScreen } from "./codirector/helpers/audit";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8761";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

expect(UI, "spec default / env must be live UI :8760").toMatch(/127\.0\.0\.1:8760|localhost:8760/);
expect(API, "spec default / env must be live API :8761").toMatch(/127\.0\.0\.1:8761|localhost:8761/);
expect(UI, "do not bounce retired :8758").not.toMatch(/:8758\b/);
expect(API, "do not bounce retired :8758").not.toMatch(/:8758\b/);

function attachHoldGuards(page: Page, clicks: { generate: boolean }) {
  page.on("request", (req) => {
    if (req.method() !== "POST") return;
    const url = req.url();
    const body = `${req.postData() || ""}`;
    const ersGenerate =
      url.includes("/executions") &&
      !url.includes("/advance") &&
      (/ers\.generate/i.test(body) || /capability["']?\s*:\s*["']ers\.generate/i.test(body));
    if (ersGenerate) {
      clicks.generate = true;
      throw new Error(`HOLD violated: blocked live Generate POST ${url}`);
    }
  });
}

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) {
      await page.waitForTimeout(200);
      continue;
    }
    const nameInput = region.getByRole("textbox", { name: /What should I call you/i }).first();
    if (await nameInput.isVisible().catch(() => false)) {
      const current = await nameInput.inputValue().catch(() => "");
      if (!current) await nameInput.fill("Tester");
    }
    for (const label of [/Save and continue/i, /Skip for now/i]) {
      const btn = region.getByRole("button", { name: label }).first();
      if ((await btn.isVisible().catch(() => false)) && !(await btn.isDisabled().catch(() => false))) {
        await btn.click({ force: true }).catch(() => undefined);
        await page.waitForTimeout(400);
        break;
      }
    }
    if (!(await region.isVisible().catch(() => false))) break;
  }
}

async function openSpatialMapTab(page: Page) {
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    const panel = page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first();
    if (await panel.isVisible().catch(() => false)) return;
    await page.waitForTimeout(800);
  }
  await expect(page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first()).toBeVisible({
    timeout: 45_000,
  });
}

test.describe("Spatial Map ERS generator selector", () => {
  test("default is Qwen; changing to GPT Image 2 does not POST", async ({ page }) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMapTab(page);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 30_000 });

    const select = page.getByTestId("ers-generator-select");
    await expect(select).toBeVisible({ timeout: 30_000 });
    await expect(select).toHaveValue("qwen2512");

    let posted = false;
    page.on("request", (req) => {
      if (req.method() !== "POST") return;
      const url = req.url();
      const body = `${req.postData() || ""}`;
      if (url.includes("/executions") && !url.includes("/advance") && /ers\.generate/i.test(body)) {
        posted = true;
      }
    });

    await select.selectOption("gpt-image-2");
    await expect(select).toHaveValue("gpt-image-2");
    await page.waitForTimeout(500);
    expect(posted, "changing the ERS generator must not POST ers.generate").toBe(false);
    expect(clicks.generate, "HOLD: Generate was not clicked").toBe(false);
  });
});
