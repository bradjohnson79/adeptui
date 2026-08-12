/**
 * Layer 3 UI — Co-Director Memory panel controls on live Beta.
 */
import { test, expect } from "@playwright/test";
import {
  createTempProject,
  deleteProject,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @codirector Layer 3 memory UI", () => {
  test("memory panel export/audit/view-source wired", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `L3-Memory-UI-${Date.now()}`);
    try {
      // Seed conversation via product API so compact/export have content
      await request.post(`http://127.0.0.1:8758/api/codirector/conversations/${project.id}/events`, {
        data: {
          events: Array.from({ length: 10 }).flatMap((_, i) => [
            {
              role: "user",
              content: `Remember bottle continuity ${i}`,
              message_id: `u-${i}-${Date.now()}`,
              client_request_id: `cr-${i}-${Date.now()}`,
              actor: "user",
            },
            {
              role: "assistant",
              content: `Keeping bottle framing ${i}`,
              message_id: `a-${i}-${Date.now()}`,
              actor: "assistant",
            },
          ]),
        },
      });

      await page.goto(`/project/${project.id}?workspace=settings`);
      await page.waitForLoadState("domcontentloaded");
      // Settings chrome may use i18n labels; force learning tab via session then click.
      await page.evaluate(() => {
        try {
          sessionStorage.setItem("adept_settings_tab", "learning");
        } catch {
          /* ignore */
        }
      });
      await page.goto(`/project/${project.id}?workspace=settings`);
      const learningTab = page
        .locator('[role="tab"], button')
        .filter({ hasText: /AI Learning|Learning|Mémoire|Apprentissage/i })
        .first();
      if (await learningTab.isVisible().catch(() => false)) {
        await learningTab.click();
      } else {
        // Fallback: click third settings tab (General, Language, AI Learning)
        await page.locator('.workspace-tabs [role="tab"], .workspace-tabs button').nth(2).click();
      }
      await expect(page.getByTestId("codirector-memory-panel")).toBeVisible({ timeout: 60_000 });
      await page.getByTestId("memory-view-source").click();
      await expect(page.getByTestId("codirector-memory-panel")).toContainText(/Memory source|projectId|revision/i, {
        timeout: 30_000,
      });
      await page.getByTestId("memory-audit").click();
      await expect(page.getByTestId("codirector-memory-panel")).toContainText(/healthy|Memory check|eventCount|foldCount/i, {
        timeout: 30_000,
      });
      await page.getByTestId("memory-compact").click();
      await expect(page.getByTestId("codirector-memory-panel")).toContainText(/summar|short|Conversation/i, {
        timeout: 30_000,
      });
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
