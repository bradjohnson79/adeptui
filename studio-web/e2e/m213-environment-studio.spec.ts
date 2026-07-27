/**
 * Focused M2.13 Environment Studio smoke (flag must be enabled in web/api env).
 */
import { test, expect } from "@playwright/test";

test.describe("M2.13 Environment Studio", () => {
  test("nav destination renders viewport chrome", async ({ page }) => {
    await page.goto("/environment-studio");
    await expect(page.getByTestId("environment-studio")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Virtual Environment Studio/i })).toBeVisible();
    await expect(page.getByTestId("m213-viewport")).toBeVisible();
  });
});
