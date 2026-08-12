/**
 * MiniMax H3 — Private Owner-Only Adept UI Smoke.
 *
 * Adept UI only — never opens ComfyUI, never POSTs to :8192 directly, never
 * copies fixtures. Exercises the private owner Route A path end-to-end through
 * the public Adept UI/API surface.
 *
 * Scenarios A–I:
 *   A — access snapshot: private on, public/Best Match/general routing off
 *   B — readiness probe (creator language, no Comfy jargon)
 *   C — real generation via /api/minimax-h3/jobs (Experimental Private Profile)
 *   D — Library asset registered after completion
 *   E — Timeline take placement when sceneId present
 *   F — cancel interrupts the runtime job
 *   G — fallback UI offered when runtime unavailable; LTX not auto-switched
 *   H — reload preserves plan/job state
 *   I — public-safety config assertions + cleanup
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import {
  MANUAL_HANDOFF_ID,
  captureHandoffSnapshot,
  createProjectViaHomeUi,
  createRunContext,
  deleteDisposableProjects,
  ensureArtifactDir,
  expectHandoffUnchanged,
  writeJson,
} from "../codirector/helpers/autonomousCert";
import { API } from "../helpers/app";

const FIXED_PROMPT =
  "A lone musician stands at a coastal observatory bathed in blue light, electronic ambience swelling around them.";

async function postJson(request: APIRequestContext, path: string, data: unknown) {
  const res = await request.post(`${API}${path}`, {
    data,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  });
  const text = await res.text();
  expect(res.ok(), `${path} -> ${res.status()} ${text.slice(0, 400)}`).toBeTruthy();
  expect(text.trim().startsWith("<")).toBeFalsy();
  return JSON.parse(text) as Record<string, any>;
}

async function getJson(request: APIRequestContext, path: string) {
  const res = await request.get(`${API}${path}`, { headers: { Accept: "application/json" } });
  const text = await res.text();
  expect(res.ok(), `${path} -> ${res.status()} ${text.slice(0, 400)}`).toBeTruthy();
  expect(text.trim().startsWith("<")).toBeFalsy();
  return JSON.parse(text) as Record<string, any>;
}

async function openTxt2Vid(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=txt2vid`);
  if (!(await page.locator("#txt2vid-engine").isVisible().catch(() => false))) {
    await page.goto(`/project/${projectId}?workspace=video`);
  }
  if (!(await page.locator("#txt2vid-engine").isVisible().catch(() => false))) {
    await page.getByText(/Text.?to.?Video|Txt2Vid/i).first().click();
  }
  await expect(page.locator("#txt2vid-engine")).toBeVisible({ timeout: 45_000 });
}

test.describe("MiniMax H3 — Private Owner-Only Adept UI Smoke", () => {
  test.describe.configure({ mode: "serial", timeout: 10 * 60_000 });

  const ctx = createRunContext();
  ctx.projectName = `H3-PRIVATE-SMOKE-${ctx.runId.replace(/^CODIRECTOR-AUTONOMOUS-CERT-/, "")}`;
  ctx.artifactDir = `docs/release-gate/minimax-h3/artifacts/private-owner-smoke/${ctx.runId.replace("CODIRECTOR", "H3-PRIVATE-SMOKE")}`;

  let projectId = "";
  let planId = "";
  let jobId = "";
  let handoffBefore: Awaited<ReturnType<typeof captureHandoffSnapshot>>;

  test.beforeAll(async ({ request }) => {
    ensureArtifactDir(ctx.artifactDir);
    handoffBefore = await captureHandoffSnapshot(request);
  });

  test.afterAll(async ({ request }) => {
    const handoffAfter = await captureHandoffSnapshot(request);
    expectHandoffUnchanged(handoffBefore, handoffAfter);
    await deleteDisposableProjects(request, ctx.createdProjectIds);
    writeJson(ctx.artifactDir, "cleanup.json", { deleted: ctx.createdProjectIds, apiBase: API });
  });

  test("A — access snapshot: private on, public/Best Match/general routing off", async ({ request }) => {
    const access = await getJson(request, "/api/minimax-h3/access");
    expect(access.privateLocalEnabled).toBe(true);
    expect(access.ownerOnly).toBe(true);
    expect(access.publicCreatorEnabled).toBe(false);
    expect(access.bestMatchEnabled).toBe(false);
    expect(access.generalRoutingEnabled).toBe(false);
    expect(access.runtimeIsIsolatedRouteA).toBe(true);
    expect(access.ownerAccessActive).toBe(true);
    // Runtime URL must be the isolated :8192 host, never production :8188.
    expect(String(access.runtimeUrl)).toContain("8192");
    expect(String(access.runtimeUrl)).not.toContain("8188");
    writeJson(ctx.artifactDir, "A-access.json", access);
  });

  test("B — readiness probe uses creator language, no Comfy jargon", async ({ request }) => {
    const readiness = await getJson(request, "/api/minimax-h3/readiness");
    writeJson(ctx.artifactDir, "B-readiness.json", readiness);
    expect(readiness.privateLocalEnabled).toBe(true);
    const blob = JSON.stringify(readiness).toLowerCase();
    expect(blob).not.toContain("comfyui");
    expect(blob).not.toContain(".safetensors");
    expect(blob).not.toContain("fl2va");
    if (readiness.ready) {
      expect(readiness.profile?.label).toBe("Experimental Private Profile");
      expect(readiness.profile?.height).toBe(256);
      expect(readiness.profile?.nativeAudio).toBe(true);
    }
  });

  test("C — real generation via /api/minimax-h3/jobs (Experimental Private Profile)", async ({ page, request }) => {
    projectId = await createProjectViaHomeUi(page, request, ctx.projectName);
    ctx.createdProjectIds.push(projectId);
    writeJson(ctx.artifactDir, "C-project.json", { projectId, name: ctx.projectName });

    // Prepare a T2VA plan via the API (creator surface).
    const prepared = await postJson(request, "/api/minimax-h3/prepare-plan", {
      projectId,
      prompt: FIXED_PROMPT,
      mode: "text-to-video",
      sourceSurface: "text-to-video",
      deployment: "local_weights",
      territory: "CA",
      durationSec: 5,
      timelineContext: null,
    });
    planId = prepared.planId;
    expect(prepared.plan.preflight?.status).toBe("ready");
    writeJson(ctx.artifactDir, "C-prepared-plan.json", prepared);

    // Submit the job through the real wired endpoint.
    const jobRes = await postJson(request, "/api/minimax-h3/jobs", {
      projectId,
      planId,
      approvalId: null,
    });
    writeJson(ctx.artifactDir, "C-job-submit.json", jobRes);
    if (jobRes.ok && jobRes.jobId) {
      jobId = jobRes.jobId;
      expect(jobRes.status).toBe("running");
      expect(jobRes.provenance?.apiUsed).toBe(false);
      expect(jobRes.provenance?.ltxUsed).toBe(false);
      expect(jobRes.provenance?.deployment).toBe("private-local");
      expect(jobRes.provenance?.access).toBe("owner-only");
    } else {
      // If the runtime is not ready, the job must be blocked honestly — never
      // faked completed. Record the honest block and skip downstream runtime
      // scenarios; fallback UI is exercised in G.
      expect(["blocked", "failed"]).toContain(jobRes.status);
      writeJson(ctx.artifactDir, "C-job-blocked.json", jobRes);
    }
  });

  test("D — Library asset registered after completion", async ({ request }) => {
    test.skip(!jobId, "No running job — runtime unavailable");
    // Poll the job until terminal.
    let job: Record<string, any> | undefined;
    await expect
      .poll(async () => {
        const res = await getJson(request, `/api/minimax-h3/jobs/${projectId}/${jobId}`);
        job = res.job;
        return job?.status;
      }, { timeout: 5 * 60_000 })
      .not.toBe("running");
    // If completed, the background finalizer imports to the Library shortly
    // after; poll until the library import receipt is visible (or timeout).
    if (job?.status === "completed") {
      await expect
        .poll(async () => {
          const res = await getJson(request, `/api/minimax-h3/jobs/${projectId}/${jobId}`);
          job = res.job;
          return job?.media?.libraryImport?.assetId;
        }, { timeout: 60_000 })
        .toBeTruthy();
    }
    writeJson(ctx.artifactDir, "D-job-final.json", job || {});
    if (job?.status === "completed") {
      expect(job.outputPath).toBeTruthy();
      expect(job.provenance?.apiUsed).toBe(false);
      expect(job.provenance?.ltxUsed).toBe(false);
      // Library import receipt must be present.
      const lib = job.media?.libraryImport;
      expect(lib?.assetId).toBeTruthy();
      expect(lib?.projectId).toBe(projectId);
      // Asset must be visible in the project library (returned via project detail).
      const projectRes = await request.get(`${API}/api/projects/${projectId}`);
      expect(projectRes.ok(), await projectRes.text()).toBeTruthy();
      const project = (await projectRes.json()) as { assets?: Array<{ id: string }> };
      const assets = project.assets || [];
      expect(assets.some((a) => a.id === lib.assetId)).toBe(true);
    } else {
      // Honest failure: record the error code, do not fake completion.
      expect(["failed", "cancelled"]).toContain(job?.status);
      writeJson(ctx.artifactDir, "D-job-not-completed.json", job || {});
    }
  });

  test("E — Timeline take placement when sceneId present", async ({ request }) => {
    test.skip(!jobId, "No running job — runtime unavailable");
    // Create a scene and re-run with sceneId to assert placement path is wired.
    const sceneRes = await request.post(`${API}/api/projects/${projectId}/scenes`, {
      data: { name: "H3 Smoke Scene", prompt: FIXED_PROMPT, duration_sec: 5 },
      headers: { "Content-Type": "application/json" },
    });
    if (!sceneRes.ok()) {
      writeJson(ctx.artifactDir, "E-scene-skip.json", { reason: "scene create unavailable" });
      test.skip();
      return;
    }
    const scene = (await sceneRes.json()) as { id: string };
    const prepared = await postJson(request, "/api/minimax-h3/prepare-plan", {
      projectId,
      prompt: FIXED_PROMPT,
      mode: "text-to-video",
      sourceSurface: "text-to-video",
      deployment: "local_weights",
      territory: "CA",
      durationSec: 5,
      timelineContext: { sceneId: scene.id, notes: [] },
    });
    const jobRes = await postJson(request, "/api/minimax-h3/jobs", {
      projectId,
      planId: prepared.planId,
    });
    writeJson(ctx.artifactDir, "E-timeline-submit.json", { sceneId: scene.id, ...jobRes });
    if (jobRes.ok && jobRes.jobId) {
      let job: Record<string, any> | undefined;
      await expect
        .poll(async () => {
          const res = await getJson(request, `/api/minimax-h3/jobs/${projectId}/${jobRes.jobId}`);
          job = res.job;
          return job?.status;
        }, { timeout: 5 * 60_000 })
        .not.toBe("running");
      if (job?.status === "completed") {
        const tl = job.provenance?.timelineImport;
        // Either placed on the scene, or a Library receipt with instructions.
        expect(tl).toBeTruthy();
        writeJson(ctx.artifactDir, "E-timeline-final.json", job || {});
      }
    }
  });

  test("F — cancel interrupts the runtime job", async ({ request }) => {
    test.skip(!jobId, "No running job — runtime unavailable");
    // Submit a fresh job, then cancel it.
    const prepared = await postJson(request, "/api/minimax-h3/prepare-plan", {
      projectId,
      prompt: FIXED_PROMPT,
      mode: "text-to-video",
      sourceSurface: "text-to-video",
      deployment: "local_weights",
      territory: "CA",
      durationSec: 5,
    });
    const jobRes = await postJson(request, "/api/minimax-h3/jobs", { projectId, planId: prepared.planId });
    if (!jobRes.ok || !jobRes.jobId) {
      writeJson(ctx.artifactDir, "F-cancel-skip.json", jobRes);
      test.skip();
      return;
    }
    const cancelRes = await postJson(request, "/api/minimax-h3/jobs/cancel", {
      projectId,
      planId: prepared.planId,
      jobId: jobRes.jobId,
      reason: "creator",
    });
    writeJson(ctx.artifactDir, "F-cancel.json", cancelRes);
    expect(cancelRes.ok).toBe(true);
    expect(cancelRes.plan?.status).toBe("cancelled");
  });

  test("G — fallback UI offered when runtime unavailable; LTX not auto-switched", async ({ page, request }) => {
    await openTxt2Vid(page, projectId);
    await page.locator("#txt2vid-engine").selectOption("minimax-h3");
    const prompt = page.locator("textarea").first();
    await prompt.fill(FIXED_PROMPT);
    await expect(page.getByTestId("minimax-h3-plan-panel")).toBeVisible();
    await page.getByTestId("minimax-h3-prepare").click();
    await expect(page.getByTestId("minimax-h3-preflight")).toBeVisible({ timeout: 30_000 });

    // If the runtime is ready, the Generate button should appear for T2VA.
    // If not ready, the LTX fallback offer must be visible and explicit.
    const generateVisible = await page.getByTestId("minimax-h3-generate").isVisible().catch(() => false);
    const fallbackVisible = await page.getByTestId("minimax-h3-ltx-fallback").isVisible().catch(() => false);
    expect(generateVisible || fallbackVisible).toBe(true);
    if (fallbackVisible) {
      // Accepting LTX must record an explicit acceptance, never auto-switch.
      await page.getByTestId("minimax-h3-accept-ltx").click();
      await expect(page.getByTestId("minimax-h3-message")).toContainText(/LTX|fallback/i, { timeout: 15_000 });
    }
    await page.screenshot({ path: `${ctx.artifactDir}/G-fallback-ui.png`, fullPage: true });
  });

  test("H — reload preserves plan/job state", async ({ page, request }) => {
    test.skip(!planId, "No plan to reload");
    // Reload the Txt2Vid workspace and confirm the plan is still retrievable.
    await openTxt2Vid(page, projectId);
    const planRes = await getJson(request, `/api/minimax-h3/plans/${projectId}/${planId}`);
    expect(planRes.ok).toBe(true);
    expect(planRes.plan?.planId).toBe(planId);
    writeJson(ctx.artifactDir, "H-reload-plan.json", planRes);
    await page.screenshot({ path: `${ctx.artifactDir}/H-reload.png`, fullPage: true });
  });

  test("I — public-safety config assertions + cleanup", async ({ request }) => {
    // Capability matrix must reflect private owner path with public disabled.
    const cap = await getJson(request, "/api/minimax-h3/capability?territory=CA");
    writeJson(ctx.artifactDir, "I-capability.json", cap);
    const local = cap.local || {};
    if (local.privateLocal) {
      expect(local.ownerOnly).toBe(true);
      expect(local.creatorEnabled).toBe(false);
      expect(local.bestMatchEnabled).toBe(false);
      expect(local.automaticRoutingEnabled).toBe(false);
      expect(local.supportsTextToVideo).toBe(true);
      expect(local.supportsImageToVideo).toBe(false);
    }
    // Protected handoff must never be mutated.
    expect(MANUAL_HANDOFF_ID).toBe("77a4b96c-8e3f-4501-897c-51bab99bedb7");
  });
});
