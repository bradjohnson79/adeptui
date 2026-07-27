import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

/**
 * M3.0h filmmaker smoke — Chromium.
 * Verifies Co-Director / Director / Editor / settings shells load for an orchestrated project.
 * Full S1–S9 packages are produced by scripts/m30h_filmmaker_scenarios.py.
 */
test.describe("M3.0h filmmaker scenario smoke", () => {
  test("Director and Editor shells load after project create", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M30H Smoke ${Date.now()}`);
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("body")).toBeVisible();

      await page.goto(`/project/${project.id}?workspace=editor`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("body")).toBeVisible();

      await page.goto(`/project/${project.id}?workspace=settings`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("body")).toBeVisible();

      expect(errors, errors.join("\n")).toEqual([]);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Approval / Co-Director surfaces do not crash on load", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M30H CD ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      await page.waitForLoadState("domcontentloaded");
      const body = page.locator("body");
      await expect(body).toBeVisible();
      // Best-effort: open Co-Director control if present
      const toggle = page.getByRole("button", { name: /co-?director/i }).first();
      if ((await toggle.count()) > 0) {
        await toggle.click().catch(() => undefined);
        await page.keyboard.press("Escape").catch(() => undefined);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
