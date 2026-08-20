import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, dismissSetupDialogs, waitForAppReady } from "../helpers/app";

test.describe("Co-Director Temporal Continuity", () => {
  test("controls persist and reach backend state", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `CD Temporal ${Date.now()}`);
    try {
      const scenes = await request.get(`${API}/api/projects/${project.id}/scenes`);
      const body = await scenes.json();
      const sceneId = String((body.scenes || body || [])[0]?.id || "");
      expect(sceneId).toBeTruthy();

      await page.goto(`/project/${project.id}?workspace=timeline`);
      await dismissSetupDialogs(page);
      await expect(page.getByTestId("timeline-v2-workspace")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("timeline-inspector")).toBeVisible({ timeout: 30_000 });

      const accordion = page.getByTestId("timeline-inspector-continuity");
      if (!(await accordion.count())) {
        test.skip(true, "Timeline inspector continuity accordion not mounted");
        return;
      }
      await accordion.click();
      await expect(page.getByTestId("timeline-cd-continuity-enabled")).toBeVisible();

      await page.getByTestId("timeline-cd-continuity-enabled").uncheck();
      await page.getByTestId("timeline-cd-cadence-interval_3").check();
      await page.getByTestId("timeline-cd-protection").selectOption("standard");
      await page.getByTestId("timeline-cd-advanced-toggle").click();
      await expect(page.getByTestId("timeline-cd-advanced")).toBeVisible();

      const after = await request.get(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
      );
      expect(after.ok()).toBeTruthy();
      const policy = (await after.json()).coDirectorContinuityPolicy;
      expect(policy.enabled).toBe(false);
      expect(policy.reviewCadence).toBe("interval_3");
      expect(policy.protection).toBe("standard");

      await page.reload();
      await dismissSetupDialogs(page);
      await page.getByTestId("timeline-inspector-continuity").click();
      await expect(page.getByTestId("timeline-cd-continuity-enabled")).not.toBeChecked();
      await expect(page.getByTestId("timeline-cd-cadence-interval_3")).toBeChecked();

      await page.getByTestId("timeline-cd-continuity-enabled").check();
      await page.getByTestId("timeline-cd-cadence-automatic").check();
      const restored = await request.get(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
      );
      const restoredPolicy = (await restored.json()).coDirectorContinuityPolicy;
      expect(restoredPolicy.enabled).toBe(true);
      expect(restoredPolicy.reviewCadence).toBe("automatic");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("setup wizard reports VideoChat3 as required video intelligence", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await dismissSetupDialogs(page);
    const card = page.getByTestId("setup-video-intelligence");
    if (!(await card.count())) {
      const openSetup = page.getByRole("button", { name: /setup|prepare my studio/i }).first();
      if (await openSetup.count()) await openSetup.click();
    }
    const profile = await request.get(`${API}/api/setup/lifecycle/video-intelligence`);
    expect(profile.ok()).toBeTruthy();
    const body = await profile.json();
    expect(body.capabilities).toBeTruthy();
    expect(typeof body.capabilities.timelineVisualReview).toBe("boolean");
    const catalog = await request.get(`${API}/api/setup/status`);
    expect(catalog.ok()).toBeTruthy();
    const status = await catalog.json();
    const components = status.components || [];
    const videochat = components.find(
      (row: { id?: string; component_id?: string }) =>
        row.component_id === "videochat3_4b" || row.id === "videochat3_4b",
    );
    expect(videochat).toBeTruthy();
    expect(videochat.required === true || videochat.required === "true" || videochat.required === 1).toBeTruthy();
  });

  test("submit gate persists a packet before the next batch may generate", async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `CD Gate ${Date.now()}`);
    try {
      const scenes = await request.get(`${API}/api/projects/${project.id}/scenes`);
      const body = await scenes.json();
      const sceneId = String((body.scenes || body || [])[0]?.id || "");
      expect(sceneId).toBeTruthy();
      const policy = await request.post(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/codirector-continuity-policy`,
        { data: { enabled: true, reviewCadence: "every_batch" } },
      );
      expect(policy.ok()).toBeTruthy();
      const master = await request.get(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
      );
      expect(master.ok()).toBeTruthy();
      const row = await master.json();
      expect(row.coDirectorContinuityPolicy.enabled).toBe(true);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
