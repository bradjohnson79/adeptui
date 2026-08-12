/**
 * M3.1a — Project Types / Templates foundation smoke (@DETERMINISTIC)
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

const OUT = path.join("artifacts", "m31a");

test.describe("M3.1a Project Types @DETERMINISTIC", () => {
  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("PROJECT-TYPE API create short_film + trailer + web_series", async ({ request }) => {
    fs.mkdirSync(OUT, { recursive: true });
    const results: Record<string, unknown> = {};

    for (const primary of ["short_film", "web_series", "video_cinematic_trailer"] as const) {
      const res = await request.post(`${API}/api/projects`, {
        data: {
          name: `M31A ${primary}`,
          primary_project_type: primary,
          project_traits: [],
          profile_overrides: {},
        },
      });
      expect(res.ok(), await res.text()).toBeTruthy();
      const project = await res.json();
      expect(project.primary_project_type).toBe(primary);

      const profileRes = await request.get(`${API}/api/projects/${project.id}/project-profile`);
      expect(profileRes.ok()).toBeTruthy();
      const profile = await profileRes.json();
      results[primary] = {
        primaryProjectType: profile.primaryProjectType,
        unitKinds: (profile.productionUnits || []).map((u: { kind: string }) => u.kind),
        libraryEmphasis: profile.resolvedProfile?.libraryEmphasis,
      };
      await deleteProject(request, project.id);
    }

    fs.writeFileSync(path.join(OUT, "project-type-api.json"), JSON.stringify(results, null, 2));
    expect((results.web_series as { unitKinds: string[] }).unitKinds).toEqual(
      expect.arrayContaining(["season", "episode"]),
    );
    expect((results.video_cinematic_trailer as { unitKinds: string[] }).unitKinds).toEqual(
      expect.arrayContaining(["trailer", "beat"]),
    );
  });

  test("LIBRARY taxonomy includes Templates and Presets", async ({ request }) => {
    const project = await createTempProject(request, "M31A Library Templates");
    try {
      const res = await request.get(`${API}/api/projects/${project.id}/library`);
      expect(res.ok()).toBeTruthy();
      const body = await res.json();
      const entry = Object.values(
        body.folderMap as Record<string, { systemKey?: string; displayPath?: string }>,
      ).find((e) => e.systemKey === "templates_presets");
      expect(entry).toBeTruthy();
      expect(String(entry?.displayPath)).toContain("Templates and Presets");
      expect(body.librarySchemaVersion).toBeGreaterThanOrEqual(2);
      fs.mkdirSync(OUT, { recursive: true });
      fs.writeFileSync(
        path.join(OUT, "library-templates-presets.json"),
        JSON.stringify(
          {
            librarySchemaVersion: body.librarySchemaVersion,
            hasTemplatesPresets: Boolean(entry),
            displayPath: entry?.displayPath,
          },
          null,
          2,
        ),
      );
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Home new-project type selector renders", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("project-type-short_film")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("project-type-video_cinematic_trailer")).toBeVisible();
    await page.getByTestId("project-type-web_series").click();
    await expect(page.getByTestId("project-subtype-web_series")).toBeVisible();
    await page.getByTestId("project-subtype-web_series").click();
    await expect(page.getByTestId("project-type-preview")).toContainText("web_series");
  });
});
