import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated codirector", () => {
  test("co-director route survives unavailable ollama without crash", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir ${Date.now()}`);

    try {
      await page.goto(`/project/${project.id}`);
      await page.goto("/co-director");
      await expect(page.locator("body")).toBeVisible();
      // Should not blank the page
      await expect(page.locator("#root")).not.toBeEmpty();

      const health = await request.get(`${API}/api/assistant/health`);
      // May be 200 with unreachable ollama — must not 5xx crash
      expect(health.status()).toBeLessThan(500);

      await page.goto(`/project/${project.id}?workspace=timeline`);
      await page.waitForTimeout(500);
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
