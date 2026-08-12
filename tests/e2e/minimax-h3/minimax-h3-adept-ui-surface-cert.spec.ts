/**
 * MiniMax H3 Adept UI surface certification.
 * Adept UI only — never opens ComfyUI, never submits workflow JSON.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import {
  MANUAL_HANDOFF_ID,
  captureHandoffSnapshot,
  createProjectViaHomeUi,
  createRunContext,
  ensureArtifactDir,
  expectHandoffUnchanged,
  writeJson,
} from "../codirector/helpers/autonomousCert";

const API = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";

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

async function openTxt2Vid(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=txt2vid`);
  // Fallback common workspace keys
  if (!(await page.locator("#txt2vid-engine").isVisible().catch(() => false))) {
    await page.goto(`/project/${projectId}?workspace=video`);
  }
  if (!(await page.locator("#txt2vid-engine").isVisible().catch(() => false))) {
    await page.getByText(/Text.?to.?Video|Txt2Vid/i).first().click();
  }
  await expect(page.locator("#txt2vid-engine")).toBeVisible({ timeout: 45_000 });
}

async function openOneFrame(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=one`);
  const panel = page.getByTestId("one-frame-panel");
  await expect(panel).toBeAttached({ timeout: 45_000 });
  await panel.scrollIntoViewIfNeeded();
  await expect(panel).toBeVisible({ timeout: 45_000 });
  return panel;
}

async function openThreeFrame(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=three`);
  const panel = page.getByTestId("three-frame-panel");
  await expect(panel).toBeAttached({ timeout: 45_000 });
  await panel.scrollIntoViewIfNeeded();
  await expect(panel).toBeVisible({ timeout: 45_000 });
  await expect(panel.getByTestId("three-frame-strip")).toBeVisible();
  return panel;
}

test.describe("MiniMax H3 Adept UI Surface Cert", () => {
  test.describe.configure({ mode: "serial", timeout: 8 * 60_000 });

  const ctx = createRunContext();
  ctx.projectName = `H3-SURFACE-CERT-${ctx.runId.replace(/^CODIRECTOR-AUTONOMOUS-CERT-/, "")}`;
  ctx.artifactDir = `docs/release-gate/minimax-h3/artifacts/${ctx.runId.replace("CODIRECTOR", "H3-SURFACE")}`;

  let projectId = "";
  let handoffBefore: Awaited<ReturnType<typeof captureHandoffSnapshot>>;

  test.beforeAll(async ({ request }) => {
    ensureArtifactDir(ctx.artifactDir);
    handoffBefore = await captureHandoffSnapshot(request);
  });

  test.afterAll(async ({ request }) => {
    const handoffAfter = await captureHandoffSnapshot(request);
    expectHandoffUnchanged(handoffBefore, handoffAfter);
    for (const id of ctx.createdProjectIds) {
      if (!id || id === MANUAL_HANDOFF_ID) continue;
      await request.delete(`${API}/api/projects/${id}`);
    }
    writeJson(ctx.artifactDir, "cleanup.json", { deleted: ctx.createdProjectIds, apiBase: API });
  });

  test("A — Co-Director tools registered (no Comfy jargon in titles)", async ({ request }) => {
    const res = await request.get(`${API}/api/codirector/tools`, {
      headers: { Accept: "application/json" },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const catalog = await res.json();
    const tools = catalog.tools as Array<{ toolId: string; title?: string; description?: string }>;
    const ids = new Set(tools.map((t) => t.toolId));
    for (const id of [
      "minimax_h3.capability",
      "minimax_h3.prepare_plan",
      "minimax_h3.prepare_three_frame",
      "minimax_h3.offer_ltx_fallback",
      "minimax_h3.accept_ltx_fallback",
    ]) {
      expect(ids.has(id), id).toBeTruthy();
    }
    const h3Tools = tools.filter((t) => t.toolId.startsWith("minimax_h3."));
    for (const tool of h3Tools) {
      const blob = `${tool.title || ""} ${tool.description || ""}`.toLowerCase();
      expect(blob.includes("comfyui")).toBeFalsy();
      expect(blob.includes(".safetensors")).toBeFalsy();
    }
  });

  test("B — Text2Video selects MiniMax H3 and prepares plan + LTX fallback", async ({ page, request }) => {
    projectId = await createProjectViaHomeUi(page, request, ctx.projectName);
    ctx.createdProjectIds.push(projectId);
    await openTxt2Vid(page, projectId);
    await page.locator("#txt2vid-engine").selectOption("minimax-h3");
    const prompt = page.locator("textarea").first();
    await prompt.fill("Cinematic rain alley push-in with quiet tension and stereo ambience.");
    await expect(page.getByTestId("minimax-h3-plan-panel")).toBeVisible();
    await page.getByTestId("minimax-h3-prepare").click();
    await expect(page.getByTestId("minimax-h3-preflight")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("minimax-h3-ltx-fallback")).toBeVisible();
    await page.getByTestId("minimax-h3-accept-ltx").click();
    await expect(page.getByTestId("minimax-h3-message")).toContainText(/LTX|fallback/i);
    await page.screenshot({ path: `${ctx.artifactDir}/B-txt2vid-h3.png`, fullPage: true });
  });

  test("C — One Frame Adept UI plan (Start Frame)", async ({ page }) => {
    const panel = await openOneFrame(page, projectId);
    const prompt = panel.getByTestId("one-frame-motion-prompt");
    await prompt.scrollIntoViewIfNeeded();
    await prompt.fill("Camera slowly pushes in from the Start Frame.");
    const prepare = panel.getByTestId("minimax-h3-prepare");
    await prepare.scrollIntoViewIfNeeded();
    await expect(prepare).toBeEnabled();
    await prepare.click();
    await expect(panel.getByTestId("minimax-h3-summary")).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: `${ctx.artifactDir}/C-one-frame-h3.png`, fullPage: true });
  });

  test("D — Three Frame segmented strategy honesty", async ({ page, request }) => {
    // Upload three tiny PNGs via API so roles are distinct
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64",
    );
    const ids: string[] = [];
    for (const name of ["start.png", "middle.png", "end.png"]) {
      const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
        multipart: {
          file: { name, mimeType: "image/png", buffer: png },
          kind: "image",
          tag: name.replace(".png", ""),
        },
      });
      if (res.ok()) {
        const body = await res.json();
        ids.push(String(body.id || body.asset_id || body.assetId || ""));
      }
    }
    // If upload shape differs, still verify three-frame plan API truth
    const planBody = await postJson(request, "/api/minimax-h3/prepare-plan", {
      projectId,
      prompt: "Walk from door to window through a midpoint beat.",
      mode: "three-frame",
      sourceSurface: "three-frame",
      deployment: "local_weights",
      territory: "US",
      durationSec: 8,
      referenceAssignments:
        ids.length === 3
          ? [
              { role: "start", assetId: ids[0], displayName: "Start Frame" },
              { role: "middle", assetId: ids[1], displayName: "Middle Guidance Frame" },
              { role: "end", assetId: ids[2], displayName: "End Frame" },
            ]
          : [
              { role: "start", assetId: "a-start", displayName: "Start Frame" },
              { role: "middle", assetId: "a-middle", displayName: "Middle Guidance Frame" },
              { role: "end", assetId: "a-end", displayName: "End Frame" },
            ],
    });
    expect(planBody.plan.advancedMetadata?.threeFrameNative ?? planBody.plan.threeFramePlan?.nativeSupported).toBeFalsy();
    expect(planBody.plan.threeFramePlan?.strategy).toBe("segmented-a");
    expect(planBody.plan.threeFramePlan?.intervals?.length).toBe(2);
    expect(JSON.stringify(planBody).toLowerCase()).not.toContain("comfyui");

    const panel = await openThreeFrame(page, projectId);
    await expect(panel.getByTestId("minimax-h3-plan-panel")).toBeVisible();
    writeJson(ctx.artifactDir, "D-three-frame-plan.json", planBody);
    await page.screenshot({ path: `${ctx.artifactDir}/D-three-frame-h3.png`, fullPage: true });
  });

  test("E — Failure/fallback: local blocked, explicit LTX, single fallback record", async ({ request }) => {
    const prepared = await postJson(request, "/api/minimax-h3/prepare-plan", {
      projectId,
      prompt: "Establishing shot of a coastal road at dusk.",
      mode: "text-to-video",
      sourceSurface: "text-to-video",
      deployment: "local_weights",
      territory: "US",
      durationSec: 6,
    });
    expect(prepared.plan.preflight.status).toBe("blocked");
    expect(prepared.plan.preflight.fallbackOffer).toBeTruthy();
    const fallback = await postJson(request, "/api/minimax-h3/fallback/ltx", {
      projectId,
      planId: prepared.planId,
      acceptedBy: "creator",
    });
    expect(fallback.message).toMatch(/LTX|auto-switch/i);
    expect(fallback.plan.fallbackOffer.accepted).toBeTruthy();
    // Jobs endpoint must not invent a completed H3 asset
    const jobRes = await request.post(`${API}/api/minimax-h3/jobs`, {
      data: { projectId, planId: prepared.planId },
      headers: { "Content-Type": "application/json" },
    });
    const jobText = await jobRes.text();
    const jobBody = jobText.startsWith("<") ? {} : JSON.parse(jobText);
    expect(JSON.stringify(jobBody).toLowerCase()).not.toContain('"status":"completed"');
    writeJson(ctx.artifactDir, "E-fallback.json", { prepared, fallback, jobBody });
  });

  test("F — Capability matrix exposes threeFrameNative false", async ({ request }) => {
    const res = await request.get(`${API}/api/minimax-h3/capability?territory=US`);
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    expect(body.local.threeFrameNative).toBe(false);
    expect(body.local.threeFrameStrategyDefault).toBe("segmented-a");
    expect(body.local.territoryAllowed).toBe(false);
    writeJson(ctx.artifactDir, "F-capability.json", body);
  });
});
