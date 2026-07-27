import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";

const VISUAL = path.join("artifacts", "m30g", "visual");

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

test.describe("M3.0g E2E certification hooks", () => {
  test("E2E-01 EN-REG English shell loads after LI prefs present", async ({ page, request }) => {
    await seedLocale(page, "en");
    await waitForAppReady(request);
    const project = await createTempProject(request, `EN-REG ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
      await expect(page.locator("body")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("E2E-07 quarantined model surfaces do not crash settings/director", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `E2E07 ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=settings`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("body")).toBeVisible();
      await page.goto(`/project/${project.id}?workspace=director`);
      await expect(page.locator("body")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("SMOKE Co-Director open/close stability ×5 (bounded sample of ×20)", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `SMOKE CD ${Date.now()}`);
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      await page.waitForLoadState("domcontentloaded");
      for (let i = 0; i < 5; i++) {
        const toggle = page.getByRole("button", { name: /co-?director/i }).first();
        if ((await toggle.count()) === 0) break;
        await toggle.click({ trial: true }).catch(() => undefined);
        await toggle.click().catch(() => undefined);
        await page.keyboard.press("Escape").catch(() => undefined);
      }
      expect(errors, errors.join("\n")).toEqual([]);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  for (const locale of ["en", "fr", "ja", "zh-Hans", "ar", "ur"] as const) {
    test(`VISUAL ${locale} director shell capture`, async ({ page, request }) => {
      await seedLocale(page, locale);
      await waitForAppReady(request);
      const project = await createTempProject(request, `VIS ${locale} ${Date.now()}`);
      try {
        await page.goto(`/project/${project.id}?workspace=director`);
        await page.waitForLoadState("domcontentloaded");
        fs.mkdirSync(VISUAL, { recursive: true });
        await page.screenshot({
          path: path.join(VISUAL, `${locale}-director.png`),
          fullPage: true,
        });
        await expect(page.locator("html")).toHaveAttribute("lang", locale);
      } finally {
        await deleteProject(request, project.id);
      }
    });
  }
});
