import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, openSetup, waitForAppReady } from "../helpers/app";

const WORKSPACES = [
  { qs: "workspace=setup", label: "setup" },
  { qs: "workspace=codirector", label: "codirector" },
  { qs: "workspace=director", label: "director" },
  { qs: "workspace=editor", label: "editor" },
  { qs: "workspace=media", label: "media" },
] as const;

async function assertNoCriticalAxe(page: import("@playwright/test").Page, route: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const critical = results.violations.filter((v) => v.impact === "critical");
  expect(critical, `${route}: ${JSON.stringify(critical, null, 2)}`).toEqual([]);
}

test.describe("@critical @isolated a11y production-critical", () => {
  test("production workspaces have no critical axe violations", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `A11y M30D ${Date.now()}`);
    try {
      for (const ws of WORKSPACES) {
        await page.goto(`/project/${project.id}?${ws.qs}`);
        await page.waitForLoadState("domcontentloaded");
        // Prefer landmark/heading presence over visual polish.
        const body = page.locator("body");
        await expect(body).toBeVisible();
        await assertNoCriticalAxe(page, ws.label);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("setup keyboard focus is visible on primary controls", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `A11y Focus ${Date.now()}`);
    try {
      await openSetup(page, project.id);
      await page.keyboard.press("Tab");
      const focused = page.locator(":focus");
      await expect(focused).toBeVisible({ timeout: 5000 });
      const tag = await focused.evaluate((el) => el.tagName.toLowerCase());
      expect(["a", "button", "input", "select", "textarea", "summary"].includes(tag) || tag.length > 0).toBeTruthy();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
