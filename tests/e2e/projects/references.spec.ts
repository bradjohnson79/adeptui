import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

/**
 * A real 1x1 PNG on disk. The upload path resizes/derives thumbnails, so a text file with a
 * .png name would exercise a different (error) branch than the one operators actually hit.
 */
const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

function writeTempPng(name: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "adept-e2e-ref-"));
  const file = path.join(dir, name);
  fs.writeFileSync(file, Buffer.from(PNG_BASE64, "base64"));
  return file;
}

test.describe("@critical @isolated references", () => {
  test("upload, attach ingredient, list, and reload", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    const project = await createTempProject(request, `E2E Refs ${Date.now()}`);
    const file = writeTempPng("hero.png");
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      await expect(page.locator(".panel.timeline").first()).toBeVisible({ timeout: 45_000 });

      // Upload through the real file input the AssetTray drives.
      await page
        .locator("input[type='file'][accept='image/*']")
        .first()
        .setInputFiles(file);

      // Assets are only exposed through the project aggregate, which is also what the UI reads.
      const projectAssets = async () => {
        const res = await request.get(`${API}/api/projects/${project.id}`);
        if (!res.ok()) return [];
        return ((await res.json()).assets || []) as { id: string; kind: string }[];
      };
      await expect
        .poll(async () => (await projectAssets()).length, { timeout: 45_000 })
        .toBeGreaterThan(0);

      const assetId = (await projectAssets())[0].id;

      // Attach as an ingredient (the project-scoped reference the compiler reads).
      const attach = await request.post(`${API}/api/projects/${project.id}/references/ingredients`, {
        data: {
          asset_id: assetId,
          role: "character",
          subject_name: "Barnes",
          priority: "primary",
        },
      });
      expect(attach.ok()).toBeTruthy();
      const ingredient = await attach.json();
      expect(ingredient.asset_id).toBe(assetId);
      expect(ingredient.subject_name).toBe("Barnes");

      const listed = await request.get(`${API}/api/projects/${project.id}/references/ingredients`);
      expect(listed.ok()).toBeTruthy();
      expect((await listed.json()).items).toHaveLength(1);

      // Reload proof: ingredients live in durable JSON, not request-scoped state.
      await page.reload();
      const afterReload = await request.get(
        `${API}/api/projects/${project.id}/references/ingredients`,
      );
      const afterItems = (await afterReload.json()).items;
      expect(afterItems).toHaveLength(1);
      expect(afterItems[0].subject_name).toBe("Barnes");

      // Honesty check: there is no DELETE for an ingredient, which is exactly why
      // `references.remove` is registered as not_implemented rather than untested.
      const remove = await request.delete(
        `${API}/api/projects/${project.id}/references/ingredients/${ingredient.id}`,
      );
      expect(remove.status()).toBeGreaterThanOrEqual(404);
      expect(remove.ok()).toBeFalsy();

      const capability = await request.get(`${API}/api/capabilities/references.remove`);
      expect(capability.ok()).toBeTruthy();
      expect((await capability.json()).status).toBe("not_implemented");

      observer.assertHealthyBrowser();
    } finally {
      fs.rmSync(path.dirname(file), { recursive: true, force: true });
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
