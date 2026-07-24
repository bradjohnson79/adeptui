import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated navigation", () => {
  test("major routes load, refresh, and back/forward", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Nav ${Date.now()}`);

    try {
      await page.goto("/");
      await page.goto(`/project/${project.id}`);
      await page.goto(`/project/${project.id}?workspace=setup`);
      await expect(page.locator(".setup-wizard-page").first()).toBeVisible({ timeout: 30_000 });
      await page.goto("/co-director");
      await page.reload();
      await expect(page.locator("#root")).not.toBeEmpty();
      await page.goBack();
      await page.goForward();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
