import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * M2.7.1 Production Executive — real Adept UI + backend + live ComfyUI + real vision.
 * provider: "local" (vision). ImageGen uses real Comfy Job+Asset (no ADEPT_MOCK_IMAGEGEN).
 * If Comfy/vision infrastructure is unavailable, tests skip with an explicit reason.
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

  /** Probe real Comfy / vision readiness. Never treat mock ImageGen as success. */
  async function realProviderStackReady(
    request: import("@playwright/test").APIRequestContext,
  ): Promise<{ ok: boolean; reason: string }> {
    try {
      const health = await waitForHealth(request);
      const caps = await request.get("/api/capabilities");
      if (!caps.ok()) {
        return {
          ok: false,
          reason: `capabilities endpoint unavailable (HTTP ${caps.status()}) — ComfyUI/vision stack not ready`,
        };
      }
      const body = await caps.json().catch(() => null);
      const list = body?.capabilities || body?.items || [];
      const comfy = Array.isArray(list)
        ? list.find(
            (c: { id?: string; name?: string }) =>
              c?.id === "comfyui.health" || String(c?.id || "").includes("comfy"),
          )
        : null;
      const comfyOk =
        comfy == null
          ? Boolean(health?.comfy?.available ?? health?.operator?.comfyAvailable)
          : Boolean(comfy.available) ||
            ["ready", "local_verified", "callable"].includes(String(comfy.status));
      if (!comfyOk) {
        return {
          ok: false,
          reason: "ComfyUI unavailable — real-provider closed-loop cannot run (mock ImageGen disabled)",
        };
      }
      return { ok: true, reason: "ok" };
    } catch (err) {
      return {
        ok: false,
        reason: `infrastructure probe failed: ${err instanceof Error ? err.message : String(err)}`,
      };
    }
  }

  async function requireRealStack(request: import("@playwright/test").APIRequestContext) {
    const probe = await realProviderStackReady(request);
    test.skip(!probe.ok, probe.reason);
  }

  async function openCoDirector(page: import("@playwright/test").Page) {
    const fab = page.locator("button.codirector-fab");
    await expect(fab).toBeVisible({ timeout: 30_000 });
    await fab.click();
    await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
  }

  async function drainWorker(request: import("@playwright/test").APIRequestContext, maxSteps = 80) {
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
        provider: "local",
        ...(idempotencyKey ? { idempotencyKey } : {}),
      },
    });
    expect(loop.ok()).toBeTruthy();
    const body = await loop.json();
    expect(body.productionContext).toBeTruthy();
    expect(body.productionContext.projectId).toBe(projectId);
    expect(body.productionContext.sceneId).toBe(sceneId);
    return body as {
      jobs: { id: string; type: string; productionContextId?: string }[];
      reused?: boolean;
      productionContext?: { id: string; projectId: string; sceneId: string };
    };
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

  test("closed loop drains to NeedsReview with real artifacts", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");
    await requireRealStack(request);

    const project = await createTempProject(request, "Production Executive NeedsReview");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-needs-review");
    const awaitJob = loopBody.jobs.find((j) => j.type === "await_approval");
    const imageJob = loopBody.jobs.find((j) => j.type === "image_generate");
    const validateJob = loopBody.jobs.find((j) => j.type === "validate");
    expect(awaitJob).toBeTruthy();

    await drainWorker(request, 120);
    const awaitInspect = await request.get(`/api/codirector/jobs/${awaitJob!.id}`);
    expect(awaitInspect.ok()).toBeTruthy();
    expect((await awaitInspect.json()).job.status).toBe("NeedsReview");

    const imgInspect = await request.get(`/api/codirector/jobs/${imageJob!.id}`);
    const imgJson = await imgInspect.json();
    expect(imgJson.job.status).toBe("Completed");
    expect(imgJson.job.result?.assetId).toBeTruthy();
    expect(imgJson.job.result?.mockAdapter).toBeFalsy();

    const valInspect = await request.get(`/api/codirector/jobs/${validateJob!.id}`);
    const valJson = await valInspect.json();
    expect(valJson.job.status).toBe("Completed");
    expect(valJson.job.result?.reportId).toBeTruthy();
    expect(valJson.job.result?.sessionId).toBeTruthy();
  });

  test("canon unchanged until mark-approval", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");
    await requireRealStack(request);

    const project = await createTempProject(request, "Production Executive PreApprove");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-preapprove");
    await drainWorker(request, 120);

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
    await requireRealStack(request);

    const project = await createTempProject(request, "Production Executive MarkApproval");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-approve");
    const awaitJob = loopBody.jobs.find((j) => j.type === "await_approval");
    expect(awaitJob).toBeTruthy();
    await drainWorker(request, 120);

    const proposalId = await proposalIdFromLoop(request, loopBody);
    const approve = await request.post(`/api/codirector/jobs/${awaitJob!.id}/mark-approval`, {
      data: { proposalId, approved: true, actor: "e2e" },
    });
    expect(approve.ok()).toBeTruthy();
    expect((await approve.json()).autoApproved).toBeFalsy();
  });

  test("Dashboard to Canon: real asset validation proposal receipt", async ({ page, request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");
    await requireRealStack(request);

    const project = await createTempProject(request, "Production Executive Full Path");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-full");
    const awaitJob = loopBody.jobs.find((j) => j.type === "await_approval");
    const applyJob = loopBody.jobs.find((j) => j.type === "apply_canon");
    const imageJob = loopBody.jobs.find((j) => j.type === "image_generate");
    expect(awaitJob).toBeTruthy();
    expect(applyJob).toBeTruthy();

    await drainWorker(request, 120);
    const imgJson = await (await request.get(`/api/codirector/jobs/${imageJob!.id}`)).json();
    expect(imgJson.job.result?.assetId).toBeTruthy();

    const proposalId = await proposalIdFromLoop(request, loopBody);
    await request.post(`/api/codirector/jobs/${awaitJob!.id}/mark-approval`, {
      data: { proposalId, approved: true, actor: "e2e" },
    });
    await drainWorker(request, 120);

    const applyJson = await (await request.get(`/api/codirector/jobs/${applyJob!.id}`)).json();
    expect(applyJson.job.status).toBe("Completed");
    expect(applyJson.job.result?.applied).toBeTruthy();
    expect(applyJson.job.result?.receiptId).toBeTruthy();

    const propRes = await request.get(
      `/api/codirector/projects/${project.id}/proposals/${proposalId}`,
    );
    expect((await propRes.json()).status).toBe("completed");

    await page.goto(`/project/${project.id}`);
    await expect(page.getByTestId("status-production-executive")).toContainText("On");
    await openCoDirector(page);
    await page.getByTestId("toggle-production-executive").click();
    await expect(page.getByTestId("production-executive-dashboard")).toBeVisible({
      timeout: 15000,
    });
    await page.getByTestId("executive-tab-history").click();
    await expect(page.getByTestId("executive-jobs-history")).toBeVisible();
  });

  test("events and audit history endpoints return data", async ({ request }) => {
    const execOn = await execEnabled(request);
    test.skip(!execOn, "production executive flag off");
    await requireRealStack(request);

    const project = await createTempProject(request, "Production Executive History");
    const loopBody = await startClosedLoop(request, project.id, "scene-e2e-history");
    const storyJob = loopBody.jobs.find((j) => j.type === "storyboard_generate");
    expect(storyJob).toBeTruthy();
    await drainWorker(request, 120);

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

  test("restart recovery documented in pytest", async () => {
    test.skip(true, "Restart recovery covered by pytest crash recovery test");
  });
});