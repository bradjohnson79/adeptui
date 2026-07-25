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

  test("scene create, read, update, delete survive reload and stay project-scoped", async ({
    request,
  }) => {
    await waitForAppReady(request);

    const own = await createTempProject(request, `E2E Scenes ${Date.now()}`);
    const other = await createTempProject(request, `E2E Scenes Other ${Date.now()}`);
    try {
      // Every new project ships with a default "Scene 1", so a created scene appends.
      const seeded = await (await request.get(`${API}/api/projects/${own.id}/scenes`)).json();
      expect(seeded).toHaveLength(1);

      const created = await request.post(`${API}/api/projects/${own.id}/scenes`, {
        data: { name: "Opening", prompt: "wide establishing shot", summary: "Act one opener" },
      });
      expect(created.ok()).toBeTruthy();
      const scene = await created.json();
      expect(scene.name).toBe("Opening");
      expect(scene.summary).toBe("Act one opener");
      expect(scene.index).toBe(1);

      // Dedicated read route (not just the project aggregate).
      const read = await request.get(`${API}/api/projects/${own.id}/scenes/${scene.id}`);
      expect(read.ok()).toBeTruthy();
      expect((await read.json()).prompt).toBe("wide establishing shot");

      // PATCH must be partial: renaming a scene may not blank its prompt.
      const patched = await request.patch(
        `${API}/api/projects/${own.id}/scenes/${scene.id}`,
        { data: { name: "Opening (rev)" } },
      );
      expect(patched.ok()).toBeTruthy();
      const patchedScene = await patched.json();
      expect(patchedScene.name).toBe("Opening (rev)");
      expect(patchedScene.prompt).toBe("wide establishing shot");
      expect(patchedScene.summary).toBe("Act one opener");

      // Reload proof: refetch from the project aggregate the UI uses on mount.
      const reloaded = await request.get(`${API}/api/projects/${own.id}`);
      expect(reloaded.ok()).toBeTruthy();
      const reloadedBody = await reloaded.json();
      expect(reloadedBody.scenes).toHaveLength(2);
      expect(reloadedBody.scenes[1].name).toBe("Opening (rev)");
      expect(reloadedBody.scenes[1].summary).toBe("Act one opener");

      // Project isolation: the sibling project must not see this scene.
      const otherScenes = await request.get(`${API}/api/projects/${other.id}/scenes`);
      expect(otherScenes.ok()).toBeTruthy();
      const otherList = await otherScenes.json();
      expect(otherList.every((s: { id: string }) => s.id !== scene.id)).toBeTruthy();
      const crossRead = await request.get(`${API}/api/projects/${other.id}/scenes/${scene.id}`);
      expect(crossRead.status()).toBe(404);

      // Indices repack after a delete so the list never shows a gap.
      const removed = await request.delete(`${API}/api/projects/${own.id}/scenes/${seeded[0].id}`);
      expect(removed.ok()).toBeTruthy();
      const afterDelete = await request.get(`${API}/api/projects/${own.id}/scenes`);
      const remaining = await afterDelete.json();
      expect(remaining).toHaveLength(1);
      expect(remaining[0].name).toBe("Opening (rev)");
      expect(remaining[0].index).toBe(0);

      const goneRead = await request.get(`${API}/api/projects/${own.id}/scenes/${seeded[0].id}`);
      expect(goneRead.status()).toBe(404);
    } finally {
      await deleteProject(request, own.id);
      await deleteProject(request, other.id);
    }
  });

  test("scene added in the UI persists across a browser reload", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    const project = await createTempProject(request, `E2E Scene UI ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      const timeline = page.locator(".panel.timeline").first();
      await expect(timeline).toBeVisible({ timeout: 45_000 });

      const before = await timeline.locator(".scene-block").count();
      await timeline.getByRole("button", { name: "Add scene" }).click();
      await expect(timeline.locator(".scene-block")).toHaveCount(before + 1, { timeout: 30_000 });

      // The API — not local component state — is the thing the reload will read back.
      await expect
        .poll(
          async () => (await (await request.get(`${API}/api/projects/${project.id}/scenes`)).json()).length,
          { timeout: 30_000 },
        )
        .toBe(before + 1);

      await page.reload();
      await expect(page.locator(".panel.timeline").first().locator(".scene-block")).toHaveCount(
        before + 1,
        { timeout: 45_000 },
      );

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
