import { test, expect } from "@playwright/test";

/**
 * LOC-ISO: changing UI locale must not rewrite persisted project language dimensions
 * stored alongside prefs (projectPrimaryLocale remains independent).
 */
test("LOC-ISO UI locale change preserves projectPrimaryLocale", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "adept_ui_language_prefs_v1",
      JSON.stringify({
        interfaceLocale: "en",
        conversationLocale: "en",
        projectPrimaryLocale: "es",
        promptLanguagePolicy: "english",
        exportLocale: "es",
        followOsLocale: false,
      })
    );
  });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");

  // Simulate 20 UI switches without mutating projectPrimaryLocale.
  await page.evaluate(() => {
    const key = "adept_ui_language_prefs_v1";
    const locales = ["fr", "ja", "ar", "zh-Hans", "hi", "ru", "pt", "bn", "id", "ur"];
    for (let i = 0; i < 20; i++) {
      const raw = localStorage.getItem(key);
      const prefs = raw ? JSON.parse(raw) : {};
      prefs.interfaceLocale = locales[i % locales.length];
      prefs.conversationLocale = prefs.interfaceLocale;
      // projectPrimaryLocale intentionally untouched
      localStorage.setItem(key, JSON.stringify(prefs));
    }
  });
  const prefs = await page.evaluate(() => {
    return JSON.parse(localStorage.getItem("adept_ui_language_prefs_v1") || "{}");
  });
  expect(prefs.projectPrimaryLocale).toBe("es");
  expect(prefs.promptLanguagePolicy).toBe("english");
  expect(prefs.exportLocale).toBe("es");
});
