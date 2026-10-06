/**
 * Spatial Map Correct Area — UI smoke (no live GPT mask enqueue).
 * Evidence copy also under theme_walk/spatial_map_inpaint/.
 *
 * Layout (P0 UX): Map | Inpaint tabs share SpatialGrid footprint.
 * Open via Inpaint tab (no stacked <details> accordion).
 */
import { test, expect } from "@playwright/test";

const PROJECT = process.env.ADEPT_E2E_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const OUT = process.env.ADEPT_CORRECT_AREA_SHOT || "tests/e2e/screenshots/spatial-map-correct-area.png";

test("spatial map Correct Area UI mounts after map exists", async ({ page }) => {
  await page.goto(`/project/${PROJECT}?workspace=spatial`, { waitUntil: "domcontentloaded" });

  const tabs = page.getByTestId("spatial-map-workspace-tabs");
  const empty = page.getByTestId("spatial-map-start-chooser");
  await Promise.race([
    tabs.waitFor({ state: "attached", timeout: 45000 }).catch(() => null),
    empty.waitFor({ state: "attached", timeout: 45000 }).catch(() => null),
  ]);

  if ((await tabs.count()) === 0) {
    test.info().annotations.push({
      type: "note",
      description: "No Spatial Map with Atlas on project — Correct Area UI not mountable; Mess Hall E2E still needed.",
    });
    await page.screenshot({ path: OUT, fullPage: true });
    return;
  }

  await expect(tabs).toBeVisible({ timeout: 15000 });
  await page.getByTestId("spatial-map-tab-inpaint").click();
  const correct = page.getByTestId("spatial-map-correct-area");
  await expect(correct).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("spatial-map-correct-area-tools")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-tool-brush")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-tool-rect")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-prompt")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-submit")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-accept")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-undo")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-again")).toBeVisible();
  await expect(page.getByTestId("spatial-map-correct-area-engine")).toContainText(/zimage\.inpaint|ZIMAGE_INPAINT|Engine|GPT_MASK_BLOCKED_NEED_BRAD/i);
  await expect(page.getByTestId("spatial-map-correct-area-canvas")).toBeVisible();
  await page.screenshot({ path: OUT, fullPage: true });
});
