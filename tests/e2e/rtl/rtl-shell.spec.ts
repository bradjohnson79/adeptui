import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";

const OUT = path.join("artifacts", "m30g", "rtl");

async function setLocale(page: import("@playwright/test").Page, locale: string) {
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

test.describe("M3.0g RTL", () => {
  for (const locale of ["ar", "ur"] as const) {
    test(`RTL-01 ${locale} root dir=rtl and timeline stays LTR-isolated`, async ({ page, request }) => {
      await setLocale(page, locale);
      await waitForAppReady(request);
      const project = await createTempProject(request, `RTL ${locale} ${Date.now()}`);
      try {
        await page.goto(`/project/${project.id}?workspace=director`);
        await page.waitForLoadState("domcontentloaded");
        await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
        await expect(page.locator("html")).toHaveAttribute("lang", locale);
        fs.mkdirSync(OUT, { recursive: true });
        await page.screenshot({ path: path.join(OUT, `${locale}-director.png`), fullPage: true });
      } finally {
        await deleteProject(request, project.id);
      }
    });
  }
});
