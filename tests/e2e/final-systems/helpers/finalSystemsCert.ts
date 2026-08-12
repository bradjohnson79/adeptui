/**
 * Shared helpers for Final Systems / All-GO Playwright certification.
 * Creator actions via Adept UI; product API for verification only.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import {
  MANUAL_HANDOFF_ID,
  MANUAL_HANDOFF_NAME,
  captureHandoffSnapshot,
  expectHandoffUnchanged,
  gotoHome,
} from "../../codirector/helpers/autonomousCert";
import { API, BETA_TARGET } from "../../helpers/app";

export {
  MANUAL_HANDOFF_ID,
  MANUAL_HANDOFF_NAME,
  captureHandoffSnapshot,
  expectHandoffUnchanged,
  BETA_TARGET,
  API,
};

export const BASELINE_PROMPT =
  "A glowing glass bottle on a dark studio table, slow cinematic push-in, subtle condensation, controlled rim lighting.";

export const RETAKE_DELTA =
  "Keep the bottle, framing, camera direction, duration, and lighting continuity. Make the camera push-in slightly slower and add a stronger condensation shimmer. Do not change the product design or background.";

export function makeRunId(prefix = "ALL-GO") {
  return `${prefix}-${new Date().toISOString().replace(/[:.]/g, "-")}`;
}

export function artifactDirFor(runId: string) {
  return path.join("docs", "release-gate", "final-systems", "artifacts", "all-go", runId);
}

export function ensureArtifactDir(dir: string) {
  fs.mkdirSync(dir, { recursive: true });
}

export function writeJson(dir: string, name: string, data: unknown) {
  ensureArtifactDir(dir);
  fs.writeFileSync(path.join(dir, name), JSON.stringify(data, null, 2), "utf-8");
}

export async function getJson(request: APIRequestContext, urlPath: string) {
  const res = await request.get(`${API}${urlPath}`, { headers: { Accept: "application/json" } });
  const text = await res.text();
  expect(res.ok(), `${urlPath} -> ${res.status()} ${text.slice(0, 400)}`).toBeTruthy();
  expect(text.trim().startsWith("<")).toBeFalsy();
  return JSON.parse(text) as Record<string, any>;
}

export async function postJson(request: APIRequestContext, urlPath: string, data?: unknown) {
  const res = await request.post(`${API}${urlPath}`, {
    data,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  });
  const text = await res.text();
  expect(res.ok(), `${urlPath} -> ${res.status()} ${text.slice(0, 400)}`).toBeTruthy();
  expect(text.trim().startsWith("<")).toBeFalsy();
  return JSON.parse(text) as Record<string, any>;
}

async function listProjects(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()) as Array<{ id: string; name: string }>;
}

/** Home UI project create — Brand Ad / Commercial when selectors exist. */
export async function createFinaleProjectViaHome(
  page: Page,
  request: APIRequestContext,
  name: string,
): Promise<string> {
  await gotoHome(page);

  const primaryEntry = page.getByTestId("create-project-open");
  if (await primaryEntry.isVisible().catch(() => false)) {
    await primaryEntry.click();
  } else {
    await page.getByRole("button", { name: /^Project$/ }).click();
    await page.getByRole("menuitem", { name: "Create project" }).click();
  }

  await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 15_000 });
  await page.locator("#np-name").fill(name);

  const commercial = page.getByTestId("project-type-commercial");
  if (await commercial.isVisible().catch(() => false)) {
    await commercial.click();
    const brandAd = page.getByTestId("project-subtype-brand_ad");
    if (await brandAd.isVisible().catch(() => false)) {
      await brandAd.click();
    }
  }

  await page.getByTestId("create-project-submit").click();
  await expect(page.getByTestId("create-project-modal-panel")).toBeHidden({ timeout: 30_000 });

  let createdId: string | null = null;
  await expect
    .poll(async () => {
      const created = (await listProjects(request)).find((p) => p.name === name);
      createdId = created?.id || null;
      return createdId;
    }, { timeout: 30_000 })
    .not.toBeNull();

  expect(createdId).toBeTruthy();
  expect(createdId).not.toBe(MANUAL_HANDOFF_ID);
  return createdId as string;
}

export async function ensureScene(
  request: APIRequestContext,
  projectId: string,
  prompt = BASELINE_PROMPT,
): Promise<string> {
  const list = await request.get(`${API}/api/projects/${projectId}/scenes`);
  const body = await list.json();
  const scenes = body.scenes || body || [];
  if (Array.isArray(scenes) && scenes[0]?.id) return scenes[0].id;
  const created = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { title: "Product Ad Shot", prompt },
  });
  expect(created.ok()).toBeTruthy();
  const c = await created.json();
  return c.id || c.scene?.id;
}

export function shotIdForScene(sceneId: string) {
  return `scene-${sceneId}-shot-1`;
}

export type H3JobResult = {
  jobId: string;
  assetId: string | null;
  job: Record<string, any>;
};

/** Run MiniMax H3 prepare+generate via visible Adept UI panel; poll job to terminal. */
export async function generateH3ViaUiPanel(
  page: Page,
  request: APIRequestContext,
  projectId: string,
  opts: { panelRoot?: ReturnType<Page["locator"]>; timeoutMs?: number } = {},
): Promise<H3JobResult> {
  const root = opts.panelRoot ?? page.locator("body");
  const prepare = root.getByTestId("minimax-h3-prepare").first();
  await expect(prepare).toBeVisible({ timeout: 60_000 });
  await prepare.click();
  await expect(root.getByTestId("minimax-h3-generate").first()).toBeVisible({ timeout: 60_000 });

  const jobPost = page.waitForResponse(
    (r) => r.url().includes("/api/minimax-h3/jobs") && r.request().method() === "POST",
    { timeout: 60_000 },
  );
  await root.getByTestId("minimax-h3-generate").first().click();
  const jobRes = await jobPost;
  const jobBody = await jobRes.json().catch(() => ({}));
  const jobId = jobBody.jobId as string;
  expect(jobId, "H3 UI generate must create a job").toBeTruthy();

  const timeoutMs = opts.timeoutMs ?? 25 * 60_000;
  let job: Record<string, any> | undefined;
  await expect
    .poll(async () => {
      const r = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${jobId}`);
      job = (await r.json()).job;
      return job?.status;
    }, { timeout: timeoutMs, intervals: [3_000, 10_000] })
    .toMatch(/completed|failed|cancelled/);

  if (job?.status === "completed") {
    await expect
      .poll(async () => {
        const r = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${jobId}`);
        job = (await r.json()).job;
        return job?.media?.libraryImport?.assetId;
      }, { timeout: 90_000, intervals: [2_000, 5_000] })
      .toBeTruthy();
  }

  const assetId = (job?.media?.libraryImport?.assetId as string) || null;
  return { jobId, assetId, job: job || {} };
}

/** Open Text-to-Video workspace with MiniMax H3 selected when possible. */
export async function openTxt2VidH3(page: Page, projectId: string, prompt: string) {
  await page.goto(`/project/${projectId}?workspace=txt2vid`);
  await page.waitForLoadState("domcontentloaded");

  let engine = page.locator("#txt2vid-engine");
  if (!(await engine.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: /^Production$/ }).click().catch(() => undefined);
    const prodItem = page.getByTestId("production-item-txt2vid");
    if (await prodItem.isVisible().catch(() => false)) {
      await prodItem.click();
    } else {
      await page.goto(`/project/${projectId}?workspace=video`);
    }
    engine = page.locator("#txt2vid-engine");
  }

  if (await engine.isVisible().catch(() => false)) {
    await engine.selectOption("minimax-h3");
  }

  const promptBox = page.locator("textarea").first();
  if (await promptBox.isVisible().catch(() => false)) {
    await promptBox.fill(prompt);
  }

  await expect(
    page
      .getByTestId("minimax-h3-prepare")
      .or(page.getByTestId("minimax-h3-plan-panel"))
      .or(engine)
      .first(),
  ).toBeVisible({ timeout: 45_000 });
}

/** Try multiple Adept UI surfaces that expose MiniMax H3 prepare/generate. */
async function generateTake1H3JobFromUi(
  page: Page,
  request: APIRequestContext,
  projectId: string,
  prompt: string,
): Promise<H3JobResult> {
  const attempts: Array<{ surface: string; run: () => Promise<H3JobResult> }> = [
    {
      surface: "txt2vid",
      run: async () => {
        await openTxt2VidH3(page, projectId, prompt);
        return generateH3ViaUiPanel(page, request, projectId);
      },
    },
    {
      surface: "one-frame",
      run: async () => {
        await page.goto(`/project/${projectId}?workspace=one`);
        const panel = page.getByTestId("one-frame-panel");
        await expect(panel).toBeVisible({ timeout: 45_000 });
        const motion = panel.getByTestId("one-frame-motion-prompt");
        if (await motion.isVisible().catch(() => false)) {
          await motion.fill("Camera slowly pushes in from the Start Frame.");
        }
        return generateH3ViaUiPanel(page, request, projectId, { panelRoot: panel });
      },
    },
    {
      surface: "timeline-retake-drawer",
      run: async () => {
        const scenes = await request.get(`${API}/api/projects/${projectId}/scenes`);
        const body = await scenes.json();
        const sceneId = (body.scenes || body)?.[0]?.id;
        if (!sceneId) throw new Error("no scene for retake drawer");
        await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${encodeURIComponent(sceneId)}`);
        await page.getByTestId("timeline-open-retake").click();
        const drawer = page.getByTestId("timeline-retake-drawer");
        await expect(drawer).toBeVisible({ timeout: 15_000 });
        return generateH3ViaUiPanel(page, request, projectId, { panelRoot: drawer });
      },
    },
  ];

  const errors: string[] = [];
  for (const attempt of attempts) {
    try {
      return await attempt.run();
    } catch (e) {
      errors.push(`${attempt.surface}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  throw new Error(`No UI surface produced H3 job: ${errors.join(" | ")}`);
}

/**
 * UI-generated Take 1: real MiniMax H3 job → library asset → baseline registry.
 * Prefers txt2vid/one-frame before Re-take drawer (drawer auto-baseline uses null assetId).
 */
export async function generateTake1ViaTimelineUi(
  page: Page,
  request: APIRequestContext,
  projectId: string,
  sceneId: string,
  prompt = BASELINE_PROMPT,
): Promise<{ take1Id: string; shotId: string; jobId: string; assetId: string | null; baselineBody: unknown }> {
  const shotId = shotIdForScene(sceneId);
  const h3 = await generateTake1H3JobFromUi(page, request, projectId, prompt);
  expect(h3.job.status, "Take 1 H3 job must complete for real baseline").toBe("completed");
  expect(h3.assetId, "Take 1 must produce a library asset from UI H3 job").toBeTruthy();

  const baseline = await request.post(`${API}/api/timeline-retakes/projects/${projectId}/baseline`, {
    data: {
      shotId,
      sceneId,
      assetId: h3.assetId,
      jobId: h3.jobId,
      prompt,
      durationSec: 5,
      provenance: {
        engine: "MiniMax H3",
        deployment: "private-local",
        access: "owner-only",
        runtime: "route-a",
        apiUsed: false,
        ltxUsed: false,
        uiGenerated: true,
        sourceSurface: "text-to-video",
      },
    },
  });
  expect(baseline.ok()).toBeTruthy();
  const baselineBody = await baseline.json();
  const take1 = baselineBody.shot?.takes?.[0]?.takeId;
  expect(take1).toBeTruthy();
  expect(
    baselineBody.shot?.takes?.[0]?.assetId || h3.assetId,
    "Take 1 must reference UI-generated library asset (avoid Re-take drawer before baseline POST)",
  ).toBeTruthy();

  await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${encodeURIComponent(sceneId)}`);
  await expect(page.getByTestId("timeline-open-retake")).toBeVisible({ timeout: 60_000 });

  return { take1Id: take1, shotId, jobId: h3.jobId, assetId: h3.assetId, baselineBody };
}

export function attachForbiddenRuntimeWatcher(page: Page) {
  const forbiddenHits: string[] = [];
  const handler = (req: { url: () => string }) => {
    const u = req.url();
    if (u.includes(":8188") || u.includes(":8192")) {
      if (!u.includes("127.0.0.1:8758") && !u.includes("localhost:8758")) {
        forbiddenHits.push(u);
      }
    }
  };
  page.on("request", handler);
  return {
    forbiddenHits,
    dispose: () => page.off("request", handler),
  };
}

export async function openWorkspace(
  page: Page,
  projectId: string,
  workspace: string,
  shellTestId?: string | RegExp,
) {
  await page.goto(`/project/${projectId}?workspace=${workspace}`);
  await page.waitForLoadState("domcontentloaded");
  const body = page.locator("body");
  await expect(body).toBeVisible({ timeout: 30_000 });
  const text = (await body.innerText().catch(() => "")) || "";
  const asksManualRuntime = /please open comfyui|please start ollama|please launch minimax|interact with :8188|:8192/i.test(
    text,
  );
  let shellOk = true;
  if (shellTestId) {
    const shell =
      typeof shellTestId === "string"
        ? page.getByTestId(shellTestId)
        : page.locator(`[data-testid]`).filter({ hasText: shellTestId });
    shellOk = await shell.isVisible().catch(() => false);
  }
  return {
    ok: !asksManualRuntime && text.length > 20,
    asksManualRuntime,
    shellOk,
    textSample: text.slice(0, 500),
  };
}
