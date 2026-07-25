import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * M2.7 Production Executive closed-loop (mocked providers).
 * Requires STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1=1 on the API under test.
 * Restart recovery is covered by pytest (test_crash_restart_recovery_no_duplicate_attempts).
 */
test.describe("Co-Director M2.7 Production Executive @critical @isolated", () => {
  async function waitForHealth(request: import("@playwright/test").APIRequestContext) {
    let lastStatus = 0;
    for (let i = 0; i < 60; i++) {
      try {
        const health = await request.get("/api/health");
        lastStatus = health.status();
        if (health.ok()) {
          return health.json();
        }
      } catch {
        /* API still booting */
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error(`API /api/health not ready (last status ${lastStatus})`);
  }

  async function execEnabled(request: import("@playwright/test").APIRequestContext) {
    const healthJson = await waitForHealth(request);
    return Boolean(healthJson?.operator?.productionExecutiveEnabled);
  }

  async function openCoDirector(page: import("@playwright/test").Page) {
    const fab = page.locator("button.codirector-fab");
    await expect(fab).toBeVisible({ timeout: 30_000 });
    await fab.click();
    await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
  }

  async function drainWorker(request: import("@playwright/test").APIRequestContext, maxSteps = 40) {
    const drain = await request.post("/api/codirector/jobs/worker/drain", {
      data: { maxSteps },
    });
    expect(drain.ok()).toBeTruthy();
    return drain.json();
  }

  async function startClosedLoop(
    request: import("@playwright/test").APIRequestContext,
    projectId: string,
    sceneId: string,
    idempotencyKey?: string,
  ) {
    const loop = await request.post("/api/codirector/jobs/closed-loop", {
      data: {
        projectId,
        sceneId,
        provider: "mock",
        ...(idempotencyKey ? { idempotencyKey } : {}),
      },
    });
    expect(loop.ok()).toBeTruthy();
    return loop.json() as Promise<{ jobs: { id: string; type: string }[]; reused?: boolean }>;
  }

  async function proposalIdFromLoop(
    request: import("@playwright/test").APIRequestContext,
    loopBody: { jobs: { id: string; type: string }[] },
  ) {
    const propJob = loopBody.jobs.find((j) => j.type === "create_proposal");
    expect(propJob).toBeTruthy();
    const propInspect = await request.get(`/api/codirector/jobs/${propJob!.id}`);
    expect(propInspect.ok()).toBeTruthy();
    const propJson = await propInspect.json();
    return propJson.job.result.proposalId as string;
  }

  test("flag off shows Off and hides dashboard", async ({ page, request }) => {
    const execOn = await execEnabled(request);
    test.skip(execOn, "production executive flag is on — flag-off UI covered when off");

    const project = await createTempProject(request, "Production Executive Flag Off");
    await page.goto(`/project/${project.id}`);
    await expect(page.getByTestId("status-production-executive")).toBeVisible();
    await expect(page.getByTestId("status-production-executive")).toContainText("Off");
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-production-executive")).toHaveCount(0);
  });

  test("closed loop drains to NeedsReview", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive NeedsReview");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-needs-review");
    const awaitJob = loopBody.jobs.find((j) => j.type === "await_approval");
    expect(awaitJob).toBeTruthy();

    await drainWorker(request);
    const awaitInspect = await request.get(`/api/codirector/jobs/${awaitJob!.id}`);
    expect(awaitInspect.ok()).toBeTruthy();
    expect((await awaitInspect.json()).job.status).toBe("NeedsReview");
  });

  test("canon unchanged until mark-approval", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive PreApprove");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-preapprove");
    await drainWorker(request);

    const applyJob = loopBody.jobs.find((j) => j.type === "apply_canon");
    expect(applyJob).toBeTruthy();
    const applyInspect = await request.get(`/api/codirector/jobs/${applyJob!.id}`);
    expect(applyInspect.ok()).toBeTruthy();
    expect((await applyInspect.json()).job.status).not.toBe("Completed");

    const proposalId = await proposalIdFromLoop(request, loopBody);
    const propRes = await request.get(
      `/api/codirector/projects/${project.id}/proposals/${proposalId}`,
    );
    expect(propRes.ok()).toBeTruthy();
    expect((await propRes.json()).status).toBe("pending");
  });

  test("mark-approval returns autoApproved false", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive MarkApproval");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-approve");
    const awaitJob = loopBody.jobs.find((j) => j.type === "await_approval");
    expect(awaitJob).toBeTruthy();
    await drainWorker(request);

    const proposalId = await proposalIdFromLoop(request, loopBody);
    const approve = await request.post(`/api/codirector/jobs/${awaitJob!.id}/mark-approval`, {
      data: { proposalId, approved: true, actor: "e2e" },
    });
    expect(approve.ok()).toBeTruthy();
    expect((await approve.json()).autoApproved).toBeFalsy();
  });

  test("after approve and drain apply completes with receipt", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive Apply");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-apply");
    const awaitJob = loopBody.jobs.find((j) => j.type === "await_approval");
    const applyJob = loopBody.jobs.find((j) => j.type === "apply_canon");
    expect(awaitJob).toBeTruthy();
    expect(applyJob).toBeTruthy();

    await drainWorker(request);
    const proposalId = await proposalIdFromLoop(request, loopBody);
    await request.post(`/api/codirector/jobs/${awaitJob!.id}/mark-approval`, {
      data: { proposalId, approved: true, actor: "e2e" },
    });
    await drainWorker(request);

    const applyInspect = await request.get(`/api/codirector/jobs/${applyJob!.id}`);
    expect(applyInspect.ok()).toBeTruthy();
    const applyJson = await applyInspect.json();
    expect(applyJson.job.status).toBe("Completed");
    expect(applyJson.job.result?.applied).toBeTruthy();
    expect(applyJson.job.result?.receiptId).toBeTruthy();

    const propRes = await request.get(
      `/api/codirector/projects/${project.id}/proposals/${proposalId}`,
    );
    expect(propRes.ok()).toBeTruthy();
    expect((await propRes.json()).status).toBe("completed");
  });

  test("events and audit history endpoints return data", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive History");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-history");
    const storyJob = loopBody.jobs.find((j) => j.type === "storyboard_generate");
    expect(storyJob).toBeTruthy();
    await drainWorker(request);

    const events = await request.get(
      `/api/codirector/jobs/events?projectId=${project.id}&jobId=${storyJob!.id}`,
    );
    expect(events.ok()).toBeTruthy();
    const eventsJson = await events.json();
    expect(Array.isArray(eventsJson.events)).toBeTruthy();

    const history = await request.get(`/api/codirector/jobs/${storyJob!.id}/history`);
    expect(history.ok()).toBeTruthy();
    const historyJson = await history.json();
    expect(historyJson.attempts.length).toBeGreaterThan(0);
    expect(historyJson.audit.length).toBeGreaterThan(0);
  });

  test("failure retry on generic job", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive Retry");
    const created = await request.post("/api/codirector/jobs", {
      data: {
        type: "generic",
        projectId: project.id,
        maxAttempts: 1,
        payload: { forceFail: true },
      },
    });
    expect(created.ok()).toBeTruthy();
    const jobId = (await created.json()).job.id;
    await drainWorker(request, 10);

    const failedInspect = await request.get(`/api/codirector/jobs/${jobId}`);
    expect(failedInspect.ok()).toBeTruthy();
    expect((await failedInspect.json()).job.status).toBe("Failed");

    const retried = await request.post(`/api/codirector/jobs/${jobId}/retry`, {
      data: { actor: "e2e", reason: "retry" },
    });
    expect(retried.ok()).toBeTruthy();
    expect((await retried.json()).job.status).toBe("Retrying");
    await drainWorker(request, 10);
    const history = await request.get(`/api/codirector/jobs/${jobId}/history`);
    expect(history.ok()).toBeTruthy();
    expect((await history.json()).attempts.length).toBeGreaterThanOrEqual(2);
    const after = await request.get(`/api/codirector/jobs/${jobId}`);
    expect((await after.json()).job.status).toBe("Failed");
  });

  test("pause and resume generic job", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive Pause");
    const created = await request.post("/api/codirector/jobs", {
      data: { type: "generic", projectId: project.id, payload: { note: "pause-me" } },
    });
    expect(created.ok()).toBeTruthy();
    const jobId = (await created.json()).job.id;

    const paused = await request.post(`/api/codirector/jobs/${jobId}/pause`, {
      data: { actor: "e2e", reason: "hold" },
    });
    expect(paused.ok()).toBeTruthy();
    expect((await paused.json()).job.status).toBe("Paused");

    const resumed = await request.post(`/api/codirector/jobs/${jobId}/resume`, {
      data: { actor: "e2e", reason: "go" },
    });
    expect(resumed.ok()).toBeTruthy();
    await drainWorker(request, 10);
    const done = await request.get(`/api/codirector/jobs/${jobId}`);
    expect((await done.json()).job.status).toBe("Completed");
  });

  test("cancel generic job", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive Cancel");
    const created = await request.post("/api/codirector/jobs", {
      data: { type: "generic", projectId: project.id, payload: { note: "cancel-me" } },
    });
    expect(created.ok()).toBeTruthy();
    const jobId = (await created.json()).job.id;

    const cancelled = await request.post(`/api/codirector/jobs/${jobId}/cancel`, {
      data: { actor: "e2e", reason: "stop" },
    });
    expect(cancelled.ok()).toBeTruthy();
    expect((await cancelled.json()).job.status).toBe("Cancelled");
  });

  test("closed-loop idempotency reuses jobs", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive Idempotency");
    const key = `e2e-idem-${Date.now()}`;
    const first = await startClosedLoop(request, project.id, "scene-e2e-idem", key);
    expect(first.reused).toBeFalsy();
    const second = await startClosedLoop(request, project.id, "scene-e2e-idem", key);
    expect(second.reused).toBeTruthy();
    expect(second.jobs.length).toBeGreaterThan(0);
  });

  test("dashboard tabs visible after successful closed loop", async ({ page, request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");

    const project = await createTempProject(request, "Production Executive Dashboard");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-ui");
    const awaitJob = loopBody.jobs.find((j) => j.type === "await_approval");
    expect(awaitJob).toBeTruthy();
    await drainWorker(request);

    const proposalId = await proposalIdFromLoop(request, loopBody);
    await request.post(`/api/codirector/jobs/${awaitJob!.id}/mark-approval`, {
      data: { proposalId, approved: true, actor: "e2e" },
    });
    await drainWorker(request);

    await page.goto(`/project/${project.id}`);
    await expect(page.getByTestId("status-production-executive")).toContainText("On");
    await openCoDirector(page);
    await page.getByTestId("toggle-production-executive").click();
    await expect(page.getByTestId("production-executive-dashboard")).toBeVisible({
      timeout: 15000,
    });
    await page.getByTestId("executive-tab-history").click();
    await expect(page.getByTestId("executive-jobs-history")).toBeVisible();
    await page.getByTestId("executive-tab-statistics").click();
    await expect(page.getByTestId("executive-statistics")).toBeVisible();
  });

  test("restart recovery documented in pytest", async () => {
    test.skip(true, "Restart recovery covered by pytest crash recovery test");
  });
});
