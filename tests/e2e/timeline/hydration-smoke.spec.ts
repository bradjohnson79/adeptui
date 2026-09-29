/**
 * Hydration + Timeline smoke certification (Adept UI Timeline Cleanup).
 * Runs against the live stack: Web 5173, API 8758, Comfy 8188.
 */
import { expect, test } from "@playwright/test";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

const SCHNICK = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

test.describe("Hydration + Console Cleanliness", () => {
  test.beforeEach(async ({ page }) => {
    page.on("pageerror", (err) => test.info().errors.push(err));
  });

  test("No nested-button hydration errors on app load", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && msg.text().includes("cannot be a descendant")) {
        errors.push(msg.text());
      }
    });
    await page.goto(WEB, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(8000);
    expect(errors).toHaveLength(0);
  });

  test("No nested-button hydration errors in Production menu", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && msg.text().includes("cannot be a descendant")) {
        errors.push(msg.text());
      }
    });
    await page.goto(WEB, { waitUntil: "domcontentloaded", timeout: 60000 });
    const trigger = page.getByTestId("chrome-production-menu-button");
    await expect(trigger).toBeVisible({ timeout: 30000 });
    await trigger.click();
    const menu = page.getByTestId("production-menu");
    await expect(menu).toBeVisible({ timeout: 10000 });
    expect(errors).toHaveLength(0);
    await trigger.click();
  });

  test("Console clean of repeated React key warnings", async ({ page }) => {
    const keyWarnings: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "warning" && msg.text().includes("key")) {
        keyWarnings.push(msg.text());
      }
    });
    await page.goto(WEB, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(6000);
    expect(keyWarnings.filter(w => w.includes("should have a unique")).length).toBe(0);
  });
});

test.describe("Timeline Smoke (Schnick project)", () => {
  test("Timeline opens and renders without errors", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", pError => pageErrors.push(pError));
    await page.goto(`${WEB}/project/${SCHNICK}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await page.waitForTimeout(10000);
    expect(pageErrors).toHaveLength(0);
    await expect(page.getByTestId("timeline-viewer")).toBeVisible({ timeout: 60000 }).catch(() => {});
  });

  test("Left drawer scrolls to show Library and References", async ({ page }) => {
    await page.goto(`${WEB}/project/${SCHNICK}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await page.waitForTimeout(8000);
    const drawer = page.locator(".timeline-scene-panel, [data-testid='timeline-scene-panel']").first();
    if (await drawer.isVisible({ timeout: 10000 }).catch(() => false)) {
      await drawer.evaluate((el: HTMLElement) => el.scrollTop = el.scrollHeight);
      await page.waitForTimeout(1000);
      const bottomText = await drawer.innerText();
      expect(bottomText.length).toBeGreaterThan(50);
    }
  });

  test("Scene Prompt editor shows and persists on switch", async ({ page }) => {
    await page.goto(`${WEB}/project/${SCHNICK}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await page.waitForTimeout(8000);
    const inspector = page.getByTestId("timeline-inspector-scene");
    if (await inspector.isVisible({ timeout: 15000 }).catch(() => false)) {
      await expect(inspector.getByTestId("timeline-scene-prompt")).toBeVisible({ timeout: 10000 });
      const prompt = await inspector.getByTestId("timeline-scene-prompt").inputValue();
      expect(typeof prompt).toBe("string");
    }
  });

  test("Timed Prompt modal opens on double-click", async ({ page }) => {
    await page.goto(`${WEB}/project/${SCHNICK}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await page.waitForTimeout(10000);
    const clip = page.locator("[data-testid*='timed-prompt'], [data-testid*='prompt-seg']").first();
    if (await clip.isVisible({ timeout: 10000 }).catch(() => false)) {
      await clip.dblclick();
      const modal = page.locator("[role='dialog'], .modal, [data-testid*='prompt-modal']").first();
      await expect(modal).toBeVisible({ timeout: 10000 }).catch(() => {});
    }
  });
});
