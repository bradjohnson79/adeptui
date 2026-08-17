import { test, expect } from "@playwright/test";

const PROJECT = "2347bf46-3762-4763-86c5-4a6032522278";
const OUT = "tests/e2e/screenshots/spatial-e2e-smoke.png";

test("spatial map live smoke", async ({ page }) => {
  await page.goto(`/project/${PROJECT}?workspace=spatial`, { waitUntil: "domcontentloaded" });
  const toggle = page.getByTestId("character-online-0");
  await expect(toggle).toBeVisible({ timeout: 25000 });
  const switchState = await toggle.getAttribute("aria-checked");
  const marker = page.locator("[data-testid^='placement-marker-']").first();
  await expect(marker).toBeVisible({ timeout: 15000 });
  const zoomIn = page.getByTestId("map-zoom-in");
  const zoomOut = page.getByTestId("map-zoom-out");
  await expect(zoomIn).toBeVisible();
  await expect(zoomOut).toBeVisible();
  await zoomIn.click();
  await zoomOut.click();
  await expect(page.getByTestId("map-toggle-grid")).toBeVisible();
  await expect(page.getByTestId("map-toggle-circles")).toBeVisible();
  await expect(page.getByTestId("map-toggle-labels")).toBeVisible();
  await expect(page.getByRole("button", { name: /Environment Reference Sheet/i })).toBeVisible();
  const atlasCount = await page.getByTestId("atlas-view-btn").count();
  const libraryBtn = await page.getByTestId("atlas-replace-btn").count();
  await page.screenshot({ path: OUT, fullPage: true });
  console.log("SMOKE switch_aria_checked=" + switchState + " marker=visible zoom_clicked=1 grid_circles_labels=visible ers=visible atlas_count=" + atlasCount + " replace_count=" + libraryBtn);
});
