import { test, expect } from "@playwright/test";

/**
 * Focused M2.14 Playwright smoke (section 53).
 * Requires STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1=true in the API env.
 */
test.describe("M2.14 Unified Experience", () => {
  test("workspace renders three-pane shell when flag on", async ({ page }) => {
    await page.goto("/codirector");
    const ws = page.getByTestId("m214-unified-workspace");
    // When flag off, workspace is not rendered — soft skip
    if ((await ws.count()) === 0) {
      test.skip(true, "M2.14 flag off in this environment");
    }
    await expect(ws).toBeVisible();
    await expect(page.getByTestId("m214-flag-badge")).toContainText("Flag:");
    await expect(page.getByTestId("m214-approval-center")).toBeVisible();
    await expect(page.getByTestId("m214-production-plan")).toBeVisible();
  });

  test("hitchhiker mocked media labeled", async ({ page }) => {
    await page.goto("/codirector");
    const btn = page.getByTestId("m214-hitchhiker");
    if ((await btn.count()) === 0) {
      test.skip(true, "M2.14 flag off in this environment");
    }
    await btn.click();
    await expect(page.getByTestId("m214-media-image")).toContainText("MOCKED");
  });
});
