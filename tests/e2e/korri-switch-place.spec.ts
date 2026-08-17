
import { test, expect } from "@playwright/test";

const PROJECT = "2347bf46-3762-4763-86c5-4a6032522278";
const OUT = "C:/AdeptFilmWorks/AIVideoStudio/tests/e2e/screenshots/korri-switch-place.png";
const OUT_SLOTS = "C:/AdeptFilmWorks/AIVideoStudio/tests/e2e/screenshots/korri-switch-slots.png";

test("place Korri with slot switch", async ({ page }) => {
  await page.goto(`/project/${PROJECT}?workspace=spatial`, { waitUntil: "domcontentloaded" });
  const toggle = page.getByTestId("character-online-0");
  await expect(toggle).toBeVisible({ timeout: 20000 });
  if ((await toggle.getAttribute("aria-checked")) !== "true") {
    await toggle.click();
  }
  await expect(toggle).toHaveAttribute("aria-checked", "true");

  const cell = page.getByTestId("cell-circle-10-10");
  await expect(cell).toBeVisible({ timeout: 10000 });
  await cell.click({ force: true });
  await expect(page.locator("[data-testid^='placement-marker-']").first()).toBeVisible({ timeout: 10000 });

  await page.screenshot({ path: OUT, fullPage: true });
  await page.getByTestId("spatial-map-slot-character-0").scrollIntoViewIfNeeded();
  await page.screenshot({ path: OUT_SLOTS, fullPage: false });
});
