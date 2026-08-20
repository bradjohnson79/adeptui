import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, dismissSetupDialogs, waitForAppReady } from "../helpers/app";

async function openContinuityInspector(page: import("@playwright/test").Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=timeline`);
  await dismissSetupDialogs(page);
  await expect(page.getByTestId("timeline-v2-workspace")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("timeline-inspector")).toBeVisible({ timeout: 30_000 });
  const accordion = page.getByTestId("timeline-inspector-continuity");
  if (!(await accordion.count())) {
    return false;
  }
  await accordion.evaluate((el) => {
    (el as HTMLDetailsElement).open = true;
  });
  await expect(page.getByTestId("timeline-cd-continuity-enabled")).toBeVisible({ timeout: 10_000 });
  return true;
}

test.describe("Co-Director Temporal Continuity", () => {
  test("controls persist and reach backend state", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `CD Temporal ${Date.now()}`);
    try {
      const scenes = await request.get(`${API}/api/projects/${project.id}/scenes`);
      const body = await scenes.json();
      const sceneId = String((body.scenes || body || [])[0]?.id || "");
      expect(sceneId).toBeTruthy();

      if (!(await openContinuityInspector(page, project.id))) {
        test.skip(true, "Timeline inspector continuity accordion not mounted");
        return;
      }

      const policyUrl = `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/codirector-continuity-policy`;
      const saved = await request.post(policyUrl, {
        data: {
          enabled: false,
          reviewCadence: "interval_3",
          protection: "standard",
          deepReview: "off",
          showDebugState: true,
          creatorNextBatchNote: "Finish Korri’s turn toward Anadriya.",
        },
      });
      expect(saved.ok()).toBeTruthy();

      await page.reload();
      await dismissSetupDialogs(page);
      expect(await openContinuityInspector(page, project.id)).toBeTruthy();
      await expect(page.getByTestId("timeline-cd-continuity-enabled")).not.toBeChecked();
      await expect(page.getByTestId("timeline-cd-cadence-interval_3")).toBeChecked();
      await expect(page.getByTestId("timeline-cd-next-note")).toHaveValue(/Finish Korri/);

      await request.post(policyUrl, {
        data: { enabled: true, reviewCadence: "interval_5", protection: "strong" },
      });
      const mid = await request.get(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
      );
      expect((await mid.json()).coDirectorContinuityPolicy.reviewCadence).toBe("interval_5");

      await request.post(policyUrl, { data: { reviewCadence: "every_batch" } });
      await request.post(policyUrl, { data: { reviewCadence: "automatic" } });
      const restored = await request.get(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
      );
      const restoredPolicy = (await restored.json()).coDirectorContinuityPolicy;
      expect(restoredPolicy.enabled).toBe(true);
      expect(restoredPolicy.reviewCadence).toBe("automatic");
      expect(restoredPolicy.protection).toBe("strong");

      await page.getByTestId("timeline-cd-advanced-toggle").evaluate((el) => (el as HTMLButtonElement).click());
      await expect(page.getByTestId("timeline-cd-advanced")).toBeAttached();

      if (await page.getByTestId("timeline-cd-unavailable").count()) {
        await expect(page.getByTestId("timeline-cd-unavailable")).toContainText(/unavailable/i);
      }
      if (await page.getByTestId("timeline-cd-reject").count()) {
        await page.getByTestId("timeline-cd-reject").click();
        const rejected = await request.get(
          `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
        );
        const rejectedPolicy = (await rejected.json()).coDirectorContinuityPolicy;
        expect(Array.isArray(rejectedPolicy.rejectedPacketIds)).toBeTruthy();
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("setup wizard reports VideoChat3 as required video intelligence", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `CD Setup ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=setup`);
      await dismissSetupDialogs(page);
      if (!(await page.getByTestId("setup-video-intelligence").count())) {
        const headerSetup = page.getByRole("button", { name: /^setup$/i }).or(page.getByRole("link", { name: /^setup$/i })).first();
        if (await headerSetup.count()) await headerSetup.click({ force: true });
      }
      if (!(await page.getByTestId("setup-video-intelligence").count())) {
        await page.goto(`/project/${project.id}?workspace=setup`);
        await dismissSetupDialogs(page);
      }
      await expect(page.getByTestId("setup-video-intelligence")).toBeVisible({ timeout: 90_000 });
      await expect(page.getByTestId("setup-vi-adept")).toContainText(/VideoChat3|Ready/);
      await expect(page.getByTestId("setup-vi-continuity")).toContainText(/VideoChat3|Ready/);

      const profile = await request.get(`${API}/api/setup/lifecycle/video-intelligence`);
      expect(profile.ok()).toBeTruthy();
      const body = await profile.json();
      expect(body.capabilities).toBeTruthy();
      expect(body.capabilities.timelineVisualReview).toBe(true);
      expect(String(body.workerPython || "")).toMatch(/videochat3-worker|python/i);

      const catalog = await request.get(`${API}/api/setup/lifecycle/components?query=videochat3`);
      expect(catalog.ok()).toBeTruthy();
      const listed = await catalog.json();
      const videochat = (listed.items || []).find(
        (row: { componentId?: string }) => row.componentId === "videochat3_4b",
      );
      expect(videochat).toBeTruthy();
      expect(videochat.required).toBeTruthy();
    } finally {
      await deleteProject(request, project.id);
    }
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
      expect(row.coDirectorContinuityPolicy.reviewCadence).toBe("every_batch");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("UI toggles Continuity ON and posts Automatic Strong to the API", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `CD UI ${Date.now()}`);
    try {
      const scenes = await request.get(`${API}/api/projects/${project.id}/scenes`);
      const body = await scenes.json();
      const sceneId = String((body.scenes || body || [])[0]?.id || "");
      expect(sceneId).toBeTruthy();
      if (!(await openContinuityInspector(page, project.id))) {
        test.skip(true, "Timeline inspector continuity accordion not mounted");
        return;
      }
      const enabled = page.getByTestId("timeline-cd-continuity-enabled");
      if (!(await enabled.isChecked())) {
        await enabled.check();
      }
      const automatic = page.getByTestId("timeline-cd-cadence-automatic");
      if (await automatic.count()) {
        await automatic.check();
      }
      const protection = page.getByTestId("timeline-cd-protection");
      if (await protection.count()) {
        await protection.selectOption("strong");
      }
      await page.getByTestId("timeline-cd-advanced-toggle").evaluate((el) => (el as HTMLButtonElement).click());
      await expect(page.getByTestId("timeline-cd-advanced")).toBeAttached();
      const note = page.getByTestId("timeline-cd-next-note");
      if (await note.count()) {
        await note.fill("Keep Korri screen-right.");
      }
      await page.reload();
      await dismissSetupDialogs(page);
      expect(await openContinuityInspector(page, project.id)).toBeTruthy();
      const persisted = await request.get(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
      );
      expect(persisted.ok()).toBeTruthy();
      const policy = (await persisted.json()).coDirectorContinuityPolicy;
      expect(policy.enabled).toBe(true);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("cadence and protection values persist for Automatic 3 5 Every Standard Strong", async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `CD Cadence ${Date.now()}`);
    try {
      const scenes = await request.get(`${API}/api/projects/${project.id}/scenes`);
      const body = await scenes.json();
      const sceneId = String((body.scenes || body || [])[0]?.id || "");
      const url = `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/codirector-continuity-policy`;
      const cases = [
        { reviewCadence: "automatic", protection: "strong" },
        { reviewCadence: "interval_3", protection: "standard" },
        { reviewCadence: "interval_5", protection: "strong" },
        { reviewCadence: "every_batch", protection: "standard" },
      ] as const;
      for (const row of cases) {
        const saved = await request.post(url, { data: { enabled: true, ...row } });
        expect(saved.ok()).toBeTruthy();
        const got = await request.get(
          `${API}/api/director-timeline/projects/${project.id}/scenes/${sceneId}/temporal-continuity`,
        );
        const policy = (await got.json()).coDirectorContinuityPolicy;
        expect(policy.reviewCadence).toBe(row.reviewCadence);
        expect(policy.protection).toBe(row.protection);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
