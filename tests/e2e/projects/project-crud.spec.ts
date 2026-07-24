import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated projects", () => {
  test("create, open, rename, persist, cleanup", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    const name = `E2E Project ${Date.now()}`;
    const project = await createTempProject(request, name);
    try {
      await page.goto("/");
      await expect(page.getByText(name)).toBeVisible({ timeout: 30_000 });

      await page.goto(`/project/${project.id}`);
      await expect(page.locator("body")).toBeVisible();

      const renamed = `${name} Renamed`;
      const patch = await request.patch(`${API}/api/projects/${project.id}`, {
        data: { name: renamed },
      });
      expect(patch.ok()).toBeTruthy();

      await page.reload();
      await page.goto("/");
      await expect(page.getByText(renamed)).toBeVisible({ timeout: 30_000 });

      // Jobs polling endpoint should respond (empty list OK)
      const jobs = await request.get(`${API}/api/projects/${project.id}/jobs`);
      expect(jobs.ok()).toBeTruthy();

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      await page.goto("/");
      await expect(page.getByText(name)).toHaveCount(0);
      observer.flush();
    }
  });
});
