/**
 * Sanitation Phase 1 — CRS card is a real image, not a black tile.
 * Reuses Schnick Coffee / Korri. Never POST /api/projects.
 */
import { expect, test } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";

test.describe("CRS sanitation card", () => {
  test("Active CRS thumbnail is a real image", async ({ page, request }) => {
    await expect
      .poll(async () => {
        try {
          return (await request.get(`${API}/api/health`, { timeout: 20_000 })).ok();
        } catch {
          return false;
        }
      }, { timeout: 60_000 })
      .toBeTruthy();

    await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${KORRI_ID}`, {
      waitUntil: "domcontentloaded",
    });
    const card = page.getByTestId("character-active-crs");
    await expect(card).toBeVisible({ timeout: 30_000 });
    const img = page.getByTestId("character-active-crs-thumb-img");
    await expect(img).toBeVisible({ timeout: 20_000 });
    await expect.poll(async () => {
      return img.evaluate((el) => (el as HTMLImageElement).naturalWidth || 0);
    }, { timeout: 20_000 }).toBeGreaterThan(8);
    const src = await img.getAttribute("src");
    expect(src || "").toContain("/api/assets/");
    expect(src || "").toMatch(/[?&]rev=/);
    await expect.poll(async () => {
      const box = await img.boundingBox();
      return box?.width || 0;
    }, { timeout: 10_000 }).toBeGreaterThan(40);
    await expect(page.getByTestId("character-active-crs-status")).toContainText("Approved");
    const revision = page.getByTestId("character-active-crs-revision");
    await expect(revision).toBeVisible();
    await expect(revision).toContainText(/Revision\s+3/);
    await expect(page.getByTestId("character-active-crs-regenerate")).toBeVisible();
    await expect(page.getByTestId("character-generate")).toBeVisible();
    // HOLD: do not click Generate or Regenerate on Schnick / Korri.
    await page.getByTestId("character-active-crs-preview").click();
    const preview = page.getByTestId("library-quick-preview");
    await expect(preview).toBeVisible({ timeout: 15_000 });
    await page.screenshot({
      path: "docs/release-gate/codirector-sanitation-phase1/evidence/crs-card-live.png",
      fullPage: true,
    });
    await page.getByTestId("library-quick-preview-close").click();
    await expect(preview).toBeHidden();
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("character-active-crs-thumb-img")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("character-active-crs-status")).toContainText("Approved");
    await expect(page.getByTestId("character-active-crs-revision")).toContainText(/Revision\s+3/);
  });
});
