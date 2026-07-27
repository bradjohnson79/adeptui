import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";

const OUT = path.join("artifacts", "m30i", "accessibility", "rtl");

async function seedLocale(page: import("@playwright/test").Page, locale: string) {
  await page.addInitScript((loc) => {
    localStorage.setItem(
      "adept_ui_language_prefs_v1",
      JSON.stringify({
        interfaceLocale: loc,
        conversationLocale: loc,
        projectPrimaryLocale: "en",
        promptLanguagePolicy: "english",
        exportLocale: loc,
        followOsLocale: false,
      })
    );
  }, locale);
}

test.describe("M3.0i RTL-A11Y", () => {
  for (const locale of ["ar", "ur"] as const) {
    test(`RTL-A11Y shell ${locale}`, async ({ page, request }) => {
      await seedLocale(page, locale);
      await waitForAppReady(request);
      const project = await createTempProject(request, `RTL ${locale} ${Date.now()}`);
      try {
        for (const ws of ["director", "editor", "settings"] as const) {
          await page.goto(`/project/${project.id}?workspace=${ws}`);
          await page.waitForLoadState("domcontentloaded");
          await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
          await expect(page.locator("html")).toHaveAttribute("lang", locale);
          for (let i = 0; i < 8; i++) await page.keyboard.press("Tab");
          const tag = await page.evaluate(() => document.activeElement?.tagName || "");
          expect(tag).not.toBe("");
        }
        fs.mkdirSync(OUT, { recursive: true });
        await page.screenshot({ path: path.join(OUT, `${locale}-director.png`), fullPage: true });
      } finally {
        await deleteProject(request, project.id);
      }
    });
  }
});
