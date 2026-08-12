/**
 * Adept Image Pipeline Foundation — autonomous Playwright certification.
 * Disposable project only. Never touch Manual Beta Handoff.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import {
  MANUAL_HANDOFF_ID,
  captureHandoffSnapshot,
  createProjectViaHomeUi,
  createRunContext,
  deleteDisposableProjects,
  deleteCertResidueByNamePrefix,
  ensureArtifactDir,
  expectHandoffUnchanged,
  writeJson,
} from "../codirector/helpers/autonomousCert";

/** Force Beta API — never resolve relative to the UI origin (8760 SPA HTML). */
const API = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";

async function postJson(request: APIRequestContext, path: string, data: unknown) {
  const res = await request.post(`${API}${path}`, {
    data,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  });
  const text = await res.text();
  expect(res.ok(), `${path} -> ${res.status()} ${text.slice(0, 400)}`).toBeTruthy();
  expect(text.trim().startsWith("<"), `${path} returned HTML instead of JSON`).toBeFalsy();
  return JSON.parse(text) as Record<string, any>;
}

async function openImageStudio(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=imagegen`);
  await expect(page.getByTestId("image-pipeline-panel")).toBeVisible({ timeout: 45_000 });
}

async function preparePlanViaUi(page: Page, prompt: string) {
  const promptBox = page.locator("textarea").first();
  await expect(promptBox).toBeVisible({ timeout: 15_000 });
  await promptBox.fill(prompt);
  await page.getByTestId("image-pipeline-prepare").click();
  await expect(page.getByTestId("image-pipeline-creative-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("image-pipeline-staging")).toBeVisible();
  await expect(page.getByTestId("image-pipeline-readiness")).toBeVisible();
}

test.describe("Image Pipeline Foundation Autonomous Cert", () => {
  test.describe.configure({ mode: "serial", timeout: 10 * 60_000 });

  const ctx = createRunContext();
  ctx.projectName = `IMAGE-PIPELINE-CERT-${ctx.runId.replace(/^CODIRECTOR-AUTONOMOUS-CERT-/, "")}`;
  ctx.artifactDir = `docs/release-gate/image-pipeline/artifacts/${ctx.runId.replace("CODIRECTOR", "IMAGE-PIPELINE")}`;

  let projectId = "";
  let handoffBefore: Awaited<ReturnType<typeof captureHandoffSnapshot>>;

  test.beforeAll(async ({ request }) => {
    ensureArtifactDir(ctx.artifactDir);
    handoffBefore = await captureHandoffSnapshot(request);
  });

  test.afterAll(async ({ request }) => {
    const handoffAfter = await captureHandoffSnapshot(request);
    expectHandoffUnchanged(handoffBefore, handoffAfter);
    for (const projectIdToDelete of ctx.createdProjectIds) {
      if (!projectIdToDelete || projectIdToDelete === MANUAL_HANDOFF_ID) continue;
      const del = await request.delete(`${API}/api/projects/${projectIdToDelete}`);
      expect([200, 204, 404]).toContain(del.status());
    }
    // Best-effort name sweep using shared helper (may use same API via env).
    await deleteDisposableProjects(request, ctx.createdProjectIds).catch(() => undefined);
    await deleteCertResidueByNamePrefix(request, "IMAGE-PIPELINE-CERT").catch(() => undefined);
    const remaining: string[] = [];
    for (const id of ctx.createdProjectIds) {
      const res = await request.get(`${API}/api/projects/${id}`);
      if (res.status() !== 404) remaining.push(id);
    }
    writeJson(ctx.artifactDir, "cleanup.json", {
      deleted: ctx.createdProjectIds,
      remaining,
      handoffId: MANUAL_HANDOFF_ID,
      handoffUnchanged: true,
      apiBase: API,
    });
    expect(remaining, `leftover disposable projects: ${remaining.join(",")}`).toEqual([]);
  });

  test("A — create disposable project and open Image Studio", async ({ page, request }) => {
    projectId = await createProjectViaHomeUi(page, request, ctx.projectName);
    ctx.createdProjectIds.push(projectId);
    expect(projectId).not.toBe(MANUAL_HANDOFF_ID);
    await openImageStudio(page, projectId);
    await page.screenshot({ path: `${ctx.artifactDir}/A-image-studio.png`, fullPage: true });
  });

  test("B — simple portrait plan (Quick, direct staging)", async ({ page }) => {
    await openImageStudio(page, projectId);
    await page.locator("#image-pipeline-quality").selectOption("quick");
    await preparePlanViaUi(
      page,
      "Quiet portrait of a lone detective looking toward camera. Soft mood. Simple single subject.",
    );
    const staging = await page.getByTestId("image-pipeline-staging").innerText();
    expect(staging.toLowerCase()).toMatch(/direct|pose|scene/);
    await page.screenshot({ path: `${ctx.artifactDir}/B-simple-portrait-plan.png`, fullPage: true });
  });

  test("C — multi-character shot recommends PoseCraft staging", async ({ page, request }) => {
    await openImageStudio(page, projectId);
    await page.locator("#image-pipeline-quality").selectOption("cinematic");
    await preparePlanViaUi(
      page,
      "Three characters in a tense reveal: Barnes foreground, Kyung and Martinez behind him, over-the-shoulder low angle, 50mm, fighting stance, eyelines off-screen.",
    );
    const staging = (await page.getByTestId("image-pipeline-staging").innerText()).toLowerCase();
    expect(staging).toMatch(/pose/);
    const creative = await page.getByTestId("image-pipeline-creative-summary").innerText();
    expect(creative.length).toBeGreaterThan(20);

    const body = await postJson(request, "/api/image-pipeline/prepare-plan?projectPolicy=Automatic", {
      projectId,
      prompt:
        "Three characters seated around a table talking, exact positions matter, over-the-shoulder, 35mm intimacy.",
      purpose: "shot",
      qualityProfile: "cinematic",
      deploymentPreference: "local",
      allowApiDeployment: false,
      characterIds: ["barnes", "kyung", "martinez"],
    });
    expect(body.plan.controlPackage.stagingRecommendation).toBe("poseCraft");
    expect(body.plan.creativeDirection.scenePurposeClass).toBeTruthy();
    expect(body.plan.modelRoute.deploymentTarget).toBe("local");
    writeJson(ctx.artifactDir, "C-multi-character-plan.json", body);
  });

  test("D — Spatial Map package honesty via API", async ({ request }) => {
    const body = await postJson(request, "/api/image-pipeline/prepare-plan?projectPolicy=Automatic", {
      projectId,
      prompt: "Establishing reverse angle of the research facility observation room looking toward the left wall.",
      purpose: "location",
      qualityProfile: "cinematic",
      deploymentPreference: "local",
      allowApiDeployment: false,
      spatialMapPayload: {
        mapId: "fixture-spatial",
        selectedDirection: "north",
        locationName: "Observation Room",
      },
    });
    const spatial = body.plan.controlPackage.spatialEnvironment;
    if (body.plan.controlPackage.stagingRecommendation === "spatialMap") {
      expect(spatial).toBeTruthy();
      expect(String(spatial.honestyNote || JSON.stringify(spatial))).toMatch(/reference|not/i);
    }
    writeJson(ctx.artifactDir, "D-spatial-plan.json", body);
  });

  test("E — candidates recommend + select without deleting others", async ({ page, request }) => {
    const prepared = await postJson(request, "/api/image-pipeline/prepare-plan", {
      projectId,
      prompt: "Cinematic three-shot with quiet tension and muted greens.",
      purpose: "shot",
      qualityProfile: "enhanced",
      deploymentPreference: "local",
      allowApiDeployment: false,
      candidateCount: 4,
    });
    const plan = prepared.plan;
    const genBody = await postJson(
      request,
      `/api/image-pipeline/plans/${projectId}/${plan.planId}/candidates/generate`,
      { candidateCount: 4 },
    );
    expect(genBody.group.candidates.length).toBe(4);
    for (const c of genBody.group.candidates) {
      if (!c.jobId) {
        expect(["draft", "blocked", "queued", "ready", "selected"]).toContain(c.status);
        expect(c.assetId == null || c.assetId === "").toBeTruthy();
      }
    }
    const recBody = await postJson(
      request,
      `/api/image-pipeline/plans/${projectId}/${plan.planId}/candidates/recommend`,
      { groupId: genBody.group.groupId },
    );
    expect(recBody.explanation).toMatch(/Candidate|pick|plan/i);
    const pickId = recBody.group.candidates[1].candidateId;
    const selBody = await postJson(
      request,
      `/api/image-pipeline/plans/${projectId}/${plan.planId}/candidates/select`,
      { groupId: genBody.group.groupId, candidateId: pickId },
    );
    expect(selBody.group.selectedCandidateId).toBe(pickId);
    expect(selBody.group.candidates.length).toBe(4);

    await openImageStudio(page, projectId);
    await preparePlanViaUi(page, "Cinematic three-shot with quiet tension and muted greens.");
    await page.getByTestId("image-pipeline-generate-candidates").click();
    await expect(page.getByTestId("image-pipeline-candidates")).toBeVisible({ timeout: 30_000 });
    writeJson(ctx.artifactDir, "E-candidates.json", { genBody, recBody, selBody });
  });

  test("F — API deployment requires approval (no silent spend)", async ({ request }) => {
    const body = await postJson(request, "/api/image-pipeline/prepare-plan", {
      projectId,
      prompt: "Poster title card with exact text ADEPT SIGNAL",
      purpose: "poster",
      qualityProfile: "studio-master",
      deploymentPreference: "api",
      allowApiDeployment: false,
    });
    expect(body.plan.modelRoute.deploymentTarget === "api" ? body.plan.modelRoute.requiresApproval : true).toBeTruthy();
    if (body.plan.modelRoute.deploymentTarget === "api") {
      expect(body.plan.modelRoute.approvedForUse).toBeFalsy();
    }
    writeJson(ctx.artifactDir, "F-api-approval.json", body);
  });

  test("G — validate + repair ladder + mastering honesty", async ({ request }) => {
    const prepared = await postJson(request, "/api/image-pipeline/prepare-plan", {
      projectId,
      prompt: "Reveal the antagonist. Audience notices eyes then weapon then doorway.",
      purpose: "shot",
      qualityProfile: "cinematic",
      deploymentPreference: "local",
      allowApiDeployment: false,
    });
    const plan = prepared.plan;
    const genBody = await postJson(
      request,
      `/api/image-pipeline/plans/${projectId}/${plan.planId}/candidates/generate`,
      { candidateCount: 2 },
    );
    const group = genBody.group;
    const candidateId = group.candidates[0].candidateId;
    const evalBody = await postJson(request, `/api/image-pipeline/plans/${projectId}/${plan.planId}/evaluate`, {
      groupId: group.groupId,
      candidateId,
    });
    expect(["pass", "warning", "fail", "not-evaluated"]).toContain(evalBody.evaluation.overallStatus);

    const repairBody = await postJson(request, `/api/image-pipeline/plans/${projectId}/${plan.planId}/repair`, {
      groupId: group.groupId,
      candidateId,
    });
    expect(Array.isArray(repairBody.instructions)).toBeTruthy();

    const masterBody = await postJson(request, `/api/image-pipeline/plans/${projectId}/${plan.planId}/master`, {
      groupId: group.groupId,
      candidateId,
      requestedAction: "upscale",
      approved: false,
    });
    const note = JSON.stringify(masterBody).toLowerCase();
    expect(
      note.includes("upscale") ||
        note.includes("master") ||
        note.includes("resize") ||
        note.includes("honest") ||
        note.includes("disclosure"),
    ).toBeTruthy();
    writeJson(ctx.artifactDir, "G-validate-repair-master.json", {
      evaluation: evalBody.evaluation,
      repairBody,
      masterBody,
    });
  });

  test("H — project isolation", async ({ page, request }) => {
    const otherName = `${ctx.projectName}-ISOLATION`;
    const otherId = await createProjectViaHomeUi(page, request, otherName);
    ctx.createdProjectIds.push(otherId);
    const res = await request.get(`${API}/api/image-pipeline/plans/${otherId}/does-not-exist`);
    expect(res.status()).toBe(404);
    const prepared = await postJson(request, "/api/image-pipeline/prepare-plan", {
      projectId: otherId,
      prompt: "Isolation check portrait",
      purpose: "concept",
      qualityProfile: "quick",
      deploymentPreference: "local",
      allowApiDeployment: false,
    });
    expect(prepared.plan.projectId).toBe(otherId);
    expect(prepared.plan.projectId).not.toBe(projectId);
  });

  test("I — Co-Director image_pipeline tools registered", async ({ request }) => {
    const catalogRes = await request.get(`${API}/api/codirector/tools`, {
      headers: { Accept: "application/json" },
    });
    expect(catalogRes.ok(), await catalogRes.text()).toBeTruthy();
    const catalog = await catalogRes.json();
    const ids = new Set((catalog.tools as { toolId: string }[]).map((t) => t.toolId));
    for (const id of [
      "image_pipeline.analyze_request",
      "image_pipeline.prepare_plan",
      "image_pipeline.prepare_creative_direction",
      "image_pipeline.generate_candidates",
      "image_pipeline.approve",
    ]) {
      expect(ids.has(id), id).toBeTruthy();
    }
  });
});
