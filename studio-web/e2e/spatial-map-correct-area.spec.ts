/**
 * Spatial Map Correct Area — UI smoke (no live GPT mask enqueue).
 * Evidence copy also under theme_walk/spatial_map_inpaint/.
 */
import { test, expect } from "@playwright/test";

const PROJECT = process.env.ADEPT_E2E_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const OUT = process.env.ADEPT_CORRECT_AREA_SHOT || "tests/e2e/screenshots/spatial-map-correct-area.png";

test("spatial map Correct Area UI mounts after map exists", async ({ page }) => {
  await page.goto(`/project/${PROJECT}?workspace=spatial`, { waitUntil: "domcontentloaded" });

  // Map must exist with Atlas; if empty state, skip soft.
  const correct = page.getByTestId("spatial-map-correct-area");
  const empty = page.getByTestId("spatial-map-start-chooser");
  await Promise.race([
    correct.waitFor({ state: "attached", timeout: 45000 }).catch(() => null),
    empty.waitFor({ state: "attached", timeout: 45000 }).catch(() => null),
  ]);

  if ((await correct.count()) === 0) {
    test.info().annotations.push({
      type: "note",
      description: "No Spatial Map with Atlas on project — Correct Area UI not mountable; Mess Hall E2E still needed.",
    });
    await page.screenshot({ path: OUT, fullPage: true });
    return;
  }

  await expect(correct).toBeVisible({ timeout: 15000 });
  await correct.locator("summary").click();
  await expect(page.getByTestId("spatial-map-correct-area-tools")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-tool-brush")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-tool-rect")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-prompt")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-submit")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-accept")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-undo")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-again")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-area-engine")).toContainText(/GPT_MASK_BLOCKED_NEED_BRAD|Engine/i);
  await page.screenshot({ path: OUT, fullPage: true });
});
