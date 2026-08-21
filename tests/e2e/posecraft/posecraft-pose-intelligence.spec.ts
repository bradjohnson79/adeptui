/**
 * Revision C Phase 2 — PoseCraft Pose Intelligence Playwright.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

async function openPoseCraft(page: Page, projectId: string) {
  await page.goto(`${WEB}/project/${projectId}?workspace=posecraft`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
}

async function putStandingScene(request: APIRequestContext, projectId: string) {
  const doc = {
    schemaVersion: 2,
    currentScene: {
      schemaVersion: 2,
      revision: 4,
      name: "Pose intelligence study",
      notes: "",
      stage: { gridSize: 12, showAxes: true, showPrimitives: true },
      camera: {
        lensMm: 35,
        aspect: "16:9",
        guides: ["safe"],
        alpha: -1.57,
        beta: 1.12,
        radius: 7.5,
        target: { x: 0, y: 1.2, z: 0 },
      },
      figures: [
        {
          id: "fig-korri",
          name: "Korri",
          archetypeId: "adult-female",
          colorId: "seaglass",
          position: { x: 0, z: 0 },
          rotationY: 20,
          scale: 1,
          pose: {},
          characterId: "char-korri",
        },
      ],
      primitives: [
        {
          id: "prim-counter",
          name: "service counter",
          kind: "table-medium",
          position: { x: 0.4, z: 0.2 },
          size: { x: 1.2, y: 0.95, z: 0.5 },
        },
      ],
      selectedFigureId: "fig-korri",
      selectedJoint: "head",
      creatorModified: true,
    },
    savedVersions: [],
    snapshots: [],
  };
  const res = await request.put(`${API}/api/posecraft/projects/${projectId}/scene`, { data: doc });
  expect(res.ok(), await res.text()).toBeTruthy();
}

test.describe("PoseCraft Pose Intelligence", () => {
  test("analyze, persist, isolate, and hand off without JEPA jargon", async ({ page, request }) => {
    await waitForAppReady(request);
    const projectA = await createTempProject(request, `Pose Intel A ${Date.now()}`);
    const projectB = await createTempProject(request, `Pose Intel B ${Date.now()}`);
    try {
      await putStandingScene(request, projectA.id);
      await putStandingScene(request, projectB.id);

      const analyzed = await request.post(`${API}/api/posecraft/projects/${projectA.id}/intelligence/analyze`, {
        data: {},
      });
      expect(analyzed.ok(), await analyzed.text()).toBeTruthy();
      const packet = (await analyzed.json()).packet;
      expect(packet.projectId).toBe(projectA.id);
      expect(packet.constraints.creatorIntentHonored).toBeTruthy();

      const latestB = await request.get(`${API}/api/posecraft/projects/${projectB.id}/intelligence`);
      expect(latestB.ok()).toBeTruthy();
      const bBody = await latestB.json();
      expect((bBody.packet || {}).packetId || "").not.toBe(packet.packetId);

      const sceneHandoff = await request.post(
        `${API}/api/posecraft/projects/${projectA.id}/intelligence/handoff/scene-creator`,
        { data: {} },
      );
      const timelineHandoff = await request.post(
        `${API}/api/posecraft/projects/${projectA.id}/intelligence/handoff/timeline`,
        { data: {} },
      );
      expect(sceneHandoff.ok(), await sceneHandoff.text()).toBeTruthy();
      expect(timelineHandoff.ok(), await timelineHandoff.text()).toBeTruthy();
      const compiled = (await timelineHandoff.json()).compiled;
      expect(compiled.applied).toBeTruthy();
      expect(String(compiled.promptPrefix || "")).toMatch(/pose continuity/i);

      await openPoseCraft(page, projectA.id);
      await expect(page.getByText(/JEPA|V-JEPA|embedding/i)).toHaveCount(0);
      const toggle = page.getByTestId("posecraft-accordion-toggle-pose-intelligence");
      if (await toggle.isVisible()) {
        const expanded = await toggle.getAttribute("aria-expanded");
        if (expanded !== "true") await toggle.click();
      }
      await expect(page.getByTestId("posecraft-analyze-pose")).toBeVisible();
      await page.getByTestId("posecraft-analyze-pose").click();
      await expect(page.getByTestId("posecraft-check-continuity")).toBeVisible();
      await expect(page.getByTestId("posecraft-send-scenecreator")).toBeVisible();
      await expect(page.getByTestId("posecraft-send-timeline")).toBeVisible();
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
      const again = page.getByTestId("posecraft-accordion-toggle-pose-intelligence");
      if (await again.isVisible()) {
        if ((await again.getAttribute("aria-expanded")) !== "true") await again.click();
      }
      await expect(page.getByTestId("posecraft-analyze-pose")).toBeVisible();
      await expect(page.getByTestId("posecraft-pose-intelligence")).toBeVisible();
    } finally {
      await deleteProject(request, projectA.id).catch(() => undefined);
      await deleteProject(request, projectB.id).catch(() => undefined);
    }
  });
});
