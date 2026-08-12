/**
 * M3.0j — Studio Project Library (deterministic API + UI tree smoke)
 * @DETERMINISTIC — no REAL_LOCAL generation
 */
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  API,
  createTempProject,
  deleteProject,
  waitForAppReady,
} from "../helpers/app";

const OUT = path.join("artifacts", "m30j", "project-library");

test.describe("M3.0j Project Library @DETERMINISTIC", () => {
  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("LIBRARY-01 API tree shape and folderMap include audio.music", async ({ request }) => {
    const project = await createTempProject(request, "M30J Library Tree");
    try {
      const res = await request.get(`${API}/api/projects/${project.id}/library`);
      expect(res.ok()).toBeTruthy();
      const body = await res.json();

      expect(body.librarySchemaVersion).toBeGreaterThan(0);
      expect(body.tree).toBeTruthy();
      expect(body.tree.systemFolderCount).toBeGreaterThan(0);
      expect(Array.isArray(body.tree.folders)).toBe(true);
      expect(body.folderMap).toBeTruthy();

      const musicEntry = Object.values(body.folderMap as Record<string, { systemKey?: string; displayPath?: string }>).find(
        (e) => e.systemKey === "audio.music",
      );
      expect(musicEntry).toBeTruthy();
      expect(String(musicEntry?.displayPath)).toContain("Audio/Music");

      fs.mkdirSync(OUT, { recursive: true });
      fs.writeFileSync(
        path.join(OUT, "api-tree-shape.json"),
        JSON.stringify(
          {
            projectId: project.id,
            librarySchemaVersion: body.librarySchemaVersion,
            systemFolderCount: body.tree.systemFolderCount,
            folderCount: body.tree.folders.length,
            hasAudioMusic: Boolean(musicEntry),
          },
          null,
          2,
        ),
      );
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("LIBRARY-02 Library workspace shows folder tree in UI", async ({ page, request }) => {
    const project = await createTempProject(request, "M30J Library UI");
    try {
      await page.goto(`/project/${project.id}?workspace=library`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByRole("heading", { name: /^Libraries$/i })).toBeVisible({
        timeout: 30_000,
      });
      await expect(page.getByRole("heading", { name: /^Folders$/i })).toBeVisible({
        timeout: 15_000,
      });

      const folderBtn = page
        .locator(".library-inspector button.linkish")
        .filter({ hasText: /Audio|Characters|Props|Scenes/i })
        .first();
      await expect(folderBtn).toBeVisible({ timeout: 20_000 });

      fs.mkdirSync(OUT, { recursive: true });
      await page.screenshot({ path: path.join(OUT, "library-folder-tree.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test.skip("LIBRARY-03 migrate/repair UI flow — REAL_LOCAL", async () => {
    // Requires operator-triggered migrate/repair with observable side effects.
  });
});
