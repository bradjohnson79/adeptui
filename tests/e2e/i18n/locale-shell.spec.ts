import { test, expect } from "@playwright/test";

/**
 * M3.0F — locale persistence + RTL dir attribute smoke.
 * Requires web app served; skips cleanly if baseURL unavailable.
 */
test.describe("M3.0F locale shell", () => {
  test("French preference sets lang and persists", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        "adept_ui_language_prefs_v1",
        JSON.stringify({
          interfaceLocale: "fr",
          conversationLocale: "fr",
          projectPrimaryLocale: "en",
          promptLanguagePolicy: "auto",
          exportLocale: "fr",
          followOsLocale: false,
        })
      );
    });
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  });

  test("Arabic preference sets rtl", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        "adept_ui_language_prefs_v1",
        JSON.stringify({
          interfaceLocale: "ar",
          conversationLocale: "ar",
          projectPrimaryLocale: "en",
          promptLanguagePolicy: "auto",
          exportLocale: "ar",
          followOsLocale: false,
        })
      );
    });
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  });
});
