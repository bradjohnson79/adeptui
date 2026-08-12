import { expect, test } from "@playwright/test";

/**
 * M42 W46 Timeline UX Rebuild — SA55 / V1–V7 smoke.
 * Creator-visible selectors preferred over hidden-only hooks.
 */

test.describe("M42 W46 Timeline UX Rebuild", () => {
  test("gate is structured and includes rebuild flags", async ({ request }) => {
    const res = await request.get("/api/director-timeline/gate");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.mock).toBe(false);
    expect(["GO", "NO-GO"]).toContain(body.verdict);
    expect(body.requiredFlags).toContain("timelineUxArchitecturePassed");
    expect(body.requiredFlags).toContain("timelineMockupParityPassed");
    expect(body.flags.timelineMockupParityPassed).toBeDefined();
  });

  test("V1/V2: Timeline shell + Scene Prompt + toolbar visible", async ({ page }) => {
    await page.goto("/");
    const projectLink = page.locator("[data-testid='project-card'], a[href*='/project/']").first();
    if ((await projectLink.count()) === 0) {
      test.skip(true, "No project available");
      return;
    }
    await projectLink.click();
    const timelineNav = page.getByRole("button", { name: /^Timeline$/i }).first();
    if ((await timelineNav.count()) === 0) {
      test.skip(true, "Timeline nav not found");
      return;
    }
    await timelineNav.click();
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("timeline-scene-header")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();
    await expect(page.getByTestId("timeline-scene-prompt")).toBeVisible();
    await expect(page.getByTestId("timeline-track-board")).toBeVisible();
    await expect(page.getByTestId("timeline-batch-lane")).toBeVisible();
    await expect(page.getByTestId("timeline-render-queue")).toBeVisible();
  });

  test("V3: Viewer resize divider present", async ({ page }) => {
    await page.goto("/");
    const projectLink = page.locator("[data-testid='project-card'], a[href*='/project/']").first();
    if ((await projectLink.count()) === 0) {
      test.skip(true, "No project available");
      return;
    }
    await projectLink.click();
    const timelineNav = page.getByRole("button", { name: /^Timeline$/i }).first();
    if ((await timelineNav.count()) === 0) {
      test.skip(true, "Timeline nav not found");
      return;
    }
    await timelineNav.click();
    await expect(page.getByTestId("timeline-monitor-divider")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("timeline-playhead")).toBeVisible();
  });
});
