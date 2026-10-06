import { expect, test } from "@playwright/test";

const PROJECT = process.env.ADEPT_CADE_PROJECT_ID || "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";
const SHIP = "a0dae8b5-7b3b-4540-bc62-f88a8c4f6358";

test("Advanced Prop cards expose Upload Approve Regenerate and source-independent PRS", async ({ page }) => {
  await page.goto(`/project/${PROJECT}?workspace=propcreator`);
  await expect(page.getByTestId("prop-creator-tab-advanced")).toBeVisible({ timeout: 30000 });
  await page.getByTestId("prop-creator-saved-select").selectOption(SHIP);
  await page.getByTestId("prop-creator-tab-advanced").click();
  await expect(page.getByTestId("prop-advanced-primary-upload")).toBeVisible({ timeout: 20000 });
  for (const angle of ["front", "back", "left", "right", "top", "bottom", "hero"]) {
    await expect(page.getByTestId(`prop-advanced-angle-${angle}`)).toBeVisible();
    await expect(page.getByTestId(`prop-advanced-angle-${angle}-upload`)).toBeEnabled();
    await expect(page.getByTestId(`prop-advanced-angle-${angle}-generate`)).toBeVisible();
    await expect(page.getByTestId(`prop-advanced-angle-${angle}-regenerate`)).toBeVisible();
    await expect(page.getByTestId(`prop-advanced-angle-${angle}-approve`)).toBeVisible();
  }
  await expect(page.getByTestId("prop-advanced-optional-views-title")).toHaveText("Additional Views (optional)");
  await expect(page.getByTestId("prop-advanced-optional-views-hint")).toContainText("Optional");
  await expect(page.getByTestId("prop-advanced-reference-sheet-generate")).toBeEnabled();
});
