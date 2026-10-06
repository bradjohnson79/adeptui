import { test, expect } from "@playwright/test";

const PROJECT = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const SCENE = "a4c85c6d-2f0e-4e49-8535-7c698306f398";
const OUT = "C:/AdeptFilmWorks/AIVideoStudio/tests/e2e/screenshots/timeline-review-extend.png";

test("Review & Extend button exists and is clickable on the Korri Timeline", async ({ page }) => {
  await page.goto(`/project/${PROJECT}?workspace=timeline&sceneId=${SCENE}`, { waitUntil: "domcontentloaded" });

  const button = page.getByTestId("timeline-header-review-extend");
  await expect(button).toBeVisible({ timeout: 20000 });
  await expect(button).toBeEnabled();

  await button.click();

  // The button may enter a busy state or the shell may surface an action notice.
  const busy = page.getByTestId("timeline-header-review-extend").locator("text=Extending");
  const notice = page.getByTestId("timeline-action-notice");
  await expect(busy.or(notice)).toBeVisible({ timeout: 10000 });

  await page.screenshot({ path: OUT, fullPage: true });
});
