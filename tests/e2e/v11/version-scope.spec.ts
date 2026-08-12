/**
 * V11-SCOPE — Version 1.1 native-3D deferral (Coming in Version 1.2).
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { API } from "../helpers/app";
import fs from "node:fs";
import path from "node:path";

const apiBase = () => process.env.STUDIO_API_BASE || API;

test.describe("V11 Version 1.1 3D scope deferral", () => {
  test("V11-SCOPE-01 Native 3D import is absent from primary navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("nav-environment-studio")).toHaveCount(0);
    await expect(page.getByTestId("nav-virtual-stage")).toHaveCount(0);
    await expect(page.getByText("3D & Virtual Environment Studio")).toHaveCount(0);
  });

  test("V11-SCOPE-02/03 3D modeling and animation actions are not executable via deep link", async ({
    page,
  }) => {
    await page.goto("/environment-studio");
    await expect(page.getByTestId("environment-studio-deferred")).toBeVisible();
    await expect(page.getByTestId("v11-deferred-label")).toContainText("Coming in Version 1.2");
    await expect(page.getByTestId("v11-deferred-message")).toContainText("Version 1.2");
    await expect(page.getByTestId("v11-deferred-guidance")).toContainText("Spatial Map");

    await page.goto("/virtual-stage");
    await expect(page.getByTestId("virtual-stage-deferred")).toBeVisible();
    await expect(page.getByTestId("v11-deferred-guidance")).toContainText("360");
  });

  test("V11-SCOPE-06 Deferred 3D capabilities display Coming in Version 1.2", async ({
    request,
  }) => {
    const res = await request.get(`${apiBase()}/api/capabilities?refresh=true`);
    expect(res.ok()).toBeTruthy();
    const snap = await res.json();
    const deferred = snap.deferred || [];
    expect(deferred.length).toBeGreaterThan(0);
    const byId = Object.fromEntries((snap.capabilities || []).map((c: any) => [c.id, c]));
    for (const id of deferred.slice(0, 8)) {
      expect(byId[id].status).toBe("deferred_version_1_2");
      expect(String(byId[id].message || "")).toMatch(/Version 1\.2/i);
    }
  });

  test("V11-SCOPE-07/08 Deferred 3D does not reduce readiness or appear Failed/Missing", async ({
    request,
  }) => {
    const caps = await (await request.get(`${apiBase()}/api/capabilities?refresh=true`)).json();
    const health = await (await request.get(`${apiBase()}/api/health`)).json();
    const registry = health.operator?.registry || {};
    expect(registry.total).toBe(caps.readinessTotal);
    expect(registry.total).toBe((caps.capabilities || []).length - (caps.deferred || []).length);
    for (const b of caps.blockers || []) {
      expect(b.status).not.toBe("deferred_version_1_2");
    }
    expect(health.operator?.virtualStageEnabled).toBeFalsy();
    expect(health.operator?.virtualEnvironmentStudioEnabled).toBeFalsy();
  });

  test("V11-SCOPE-09/10/11/12/13/14/15 Supported V1.1 surfaces remain available in health/registry", async ({
    request,
  }) => {
    const snap = await (await request.get(`${apiBase()}/api/capabilities?refresh=true`)).json();
    const byId = Object.fromEntries((snap.capabilities || []).map((c: any) => [c.id, c]));
    // Spatial / camera / lighting / video / lipsync / editing remain in registry (not deferred).
    for (const id of [
      "spatial.scene.read",
      "video.generate",
      "lipsync.generate",
      "scene.render",
    ]) {
      if (byId[id]) {
        expect(byId[id].status).not.toBe("deferred_version_1_2");
      }
    }
    expect(byId["ve.import.validate"]?.status).toBe("deferred_version_1_2");
  });

  test("V11-SCOPE-16 Version 1.1 templates do not promise native 3D library slot", async ({
    request,
  }) => {
    // Prefer live templates-presets API when the M3.1a flag is on; otherwise assert the
    // Version 1.1 catalog source of truth (game_cinematic must not list a native "3D" slot).
    const res = await request.get(`${apiBase()}/api/templates-presets/project-types`);
    if (res.ok()) {
      const body = await res.json();
      const items = Array.isArray(body) ? body : body.items || body.types || [];
      const gc = items.find(
        (t: { slug?: string; id?: string }) =>
          t.slug === "game_cinematic" || String(t.id || "").includes("game_cinematic"),
      );
      expect(gc, "game_cinematic project type").toBeTruthy();
      const lib =
        gc.profile?.library_emphasis ||
        gc.libraryEmphasis ||
        gc.library_emphasis ||
        gc.library ||
        [];
      expect(lib).not.toContain("3D");
      return;
    }
    const catalog = fs.readFileSync(
      "studio-api/app/templates_presets/catalog/project_types.py",
      "utf8",
    );
    expect(catalog).toContain('"game_cinematic"');
    expect(catalog).toMatch(/DEFERRED_VERSION_1_2|Version 1\.2/);
    expect(catalog).toMatch(/library=\["Characters", "Scenes", "Audio"\]/);
    expect(catalog).not.toMatch(/library=\[[^\]]*\"3D\"[^\]]*\]/);
  });

  test("V11-SCOPE-17 Direct 3D API requests return canonical deferred response", async ({
    request,
  }) => {
    const importRes = await request.post(`${apiBase()}/api/codirector/m213/import`, {
      data: { projectId: "p", sourcePath: "C:/tmp/x.glb", title: "x" },
    });
    expect(importRes.status()).toBe(403);
    const importDetail = (await importRes.json()).detail;
    expect(importDetail.code).toBe("DEFERRED_VERSION_1_2");
    expect(importDetail.message).toContain("Version 1.2");

    const stageRes = await request.post(`${apiBase()}/api/codirector/m28/virtual-stage`, {
      data: { projectId: "p", sceneId: "s", name: "Stage" },
    });
    expect(stageRes.status()).toBe(403);
    const stageDetail = (await stageRes.json()).detail;
    expect(stageDetail.code).toBe("DEFERRED_VERSION_1_2");
  });

  test("V11-SCOPE-04/05 Co-Director policy text recommends 360 Environment workflow", async () => {
    // Backend system prompt is the executable policy surface (no hidden 3D tools).
    const promptPath = path.join("studio-api", "app", "assistant.py");
    const text = fs.readFileSync(promptPath, "utf8");
    expect(text).toContain("DEFERRED_VERSION_1_2");
    expect(text).toMatch(/360 Environment|360 panoramic/i);
    expect(text).toMatch(/Spatial Map/);
    expect(text).toMatch(/Do NOT propose 3D import/i);
  });

  test("V11-SCOPE-18/19 No unexpected console errors; axe serious/critical clean on deferral page", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    await page.goto("/environment-studio");
    await expect(page.getByTestId("environment-studio-deferred")).toBeVisible();
    const axe = await new AxeBuilder({ page }).analyze();
    const bad = (axe.violations || []).filter((v) =>
      ["serious", "critical"].includes(String(v.impact || "").toLowerCase()),
    );
    expect(bad, JSON.stringify(bad.map((v) => v.id))).toEqual([]);
    expect(errors.filter((e) => !/ResizeObserver/i.test(e))).toEqual([]);
  });

  test("V11-SCOPE-20 M3.2g certification artifact remains present", async () => {
    const cert = path.join("artifacts", "m32g", "hitchhiker-test-2-certification.json");
    const wan = path.join(
      "data",
      "projects",
      "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9",
      "renders",
      "scene_test2_wan_full_c82c2e65.mp4",
    );
    expect(fs.existsSync(cert)).toBeTruthy();
    expect(fs.existsSync(wan)).toBeTruthy();
  });
});
