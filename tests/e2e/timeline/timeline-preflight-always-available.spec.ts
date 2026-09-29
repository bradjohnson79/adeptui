/**
 * Timeline Preflight stays visible and runnable without Co-Director chat.
 * Reuses Korri Anadriya. Disposable scene only — never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const UI = process.env.ADEPT_UI_ORIGIN || "http://127.0.0.1:5173";
const SCENE_NAME = "Preflight Always Available Cert";

async function getJson(request: APIRequestContext, path: string) {
  const res = await request.get(`${API}${path}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function openRightInspector(page: Page) {
  const rightToggle = page.getByTestId("timeline-drawer-right-toggle");
  await expect(rightToggle).toBeVisible();
  if ((await rightToggle.getAttribute("aria-expanded")) !== "true") {
    await rightToggle.click();
  }
  await expect(rightToggle).toHaveAttribute("aria-expanded", "true");
  const tab = page.getByTestId("timeline-tab-inspector");
  if (await tab.isVisible().catch(() => false)) await tab.click();
  await expect(page.getByTestId("timeline-inspector")).toBeVisible({ timeout: 20_000 });
}

async function cleanupTempScenes(request: APIRequestContext) {
  const project = await getJson(request, `/api/projects/${PROJECT_ID}`);
  for (const scene of project.scenes || []) {
    if (String(scene.name || "").startsWith(SCENE_NAME)) {
      await request.delete(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}`);
    }
  }
}

test.describe("Timeline Preflight always available", () => {
  test.setTimeout(180_000);
  test.skip(process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1", "Requires ADEPT_ALLOW_KORRI_MUTATION=1");

  test("header + inspector Preflight survive Batch selection and reload", async ({ page, request }) => {
    await expect
      .poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 })
      .toBeTruthy();
    await cleanupTempScenes(request);

    const created = await request.post(`${API}/api/projects/${PROJECT_ID}/scenes`, {
      data: { name: SCENE_NAME, engine: "minimax-h3", duration_sec: 5, prompt: "Preflight cert" },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const scene = await created.json();
    const sceneId = scene.id as string;

    try {
      let master = await getJson(request, `/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`);
      let batch = (master.master || master).batchBlocks?.[0];
      if (!batch?.id) {
        const added = await request.post(
          `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/batches`,
          { data: { plannedDuration: 5 } },
        );
        expect(added.ok(), await added.text()).toBeTruthy();
        master = await getJson(request, `/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`);
        batch = (master.master || master).batchBlocks?.[0];
      }

      await page.goto(`${UI}/project/${PROJECT_ID}?workspace=timeline&sceneId=${sceneId}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("timeline-header-preflight")).toBeVisible();
      await expect(page.getByTestId("timeline-toolbar-preflight")).toBeVisible();
      await openRightInspector(page);

      const inspectorBtn = page.getByTestId("timeline-inspector-preflight");
      await expect(page.getByTestId("scene-readiness-panel")).toBeVisible();
      await expect(inspectorBtn).toBeVisible();
      await expect(inspectorBtn).toHaveText(/Preflight|Checking/);

      const persist = page.waitForResponse(
        (res) =>
          res.url().includes(`/scenes/${sceneId}/preflight`) &&
          res.request().method() === "GET" &&
          res.ok(),
        { timeout: 30_000 },
      );
      await inspectorBtn.click();
      const preflightRes = await persist;
      const body = await preflightRes.json();
      expect(Array.isArray(body.findings)).toBeTruthy();
      expect(body.productionReadiness?.sceneId || body.productionReadiness).toBeTruthy();

      await expect
        .poll(async () => {
          const pkg = await getJson(
            request,
            `/api/codirector/projects/${PROJECT_ID}/production-lifecycle/scenes/${sceneId}/package`,
          );
          return pkg.error !== "Scene not found";
        }, { timeout: 15_000 })
        .toBeTruthy();

      await expect(page.getByTestId("scene-readiness-status")).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("scene-readiness-blocker")).not.toContainText("run Co-Director Preflight");

      if (batch?.id) {
        await page.getByTestId(`timeline-batch-${batch.id}`).click();
        await expect(page.getByTestId("timeline-batch-inspector")).toBeVisible({ timeout: 20_000 });
        await expect(page.getByTestId("timeline-inspector-preflight")).toBeVisible();
        await expect(page.getByTestId("scene-readiness-panel")).toBeVisible();
      }

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("timeline-header-preflight")).toBeVisible();
      await openRightInspector(page);
      await expect(page.getByTestId("timeline-inspector-preflight")).toBeVisible();
    } finally {
      await request.delete(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}`);
    }
  });
});
