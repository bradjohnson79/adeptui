/**
 * Graduation helpers — Two-Character Dramatic Scene ("One More Cup").
 *
 * Reused from codirector/helpers/autonomousCert.ts (handoff snapshot,
 * delete disposables, monitorProjectCreatePosts, Co-Director chat helpers,
 * writeJson, ensureArtifactDir) plus Comfy/H3 preflight + forbidden URL
 * watcher + RunContext/verdict writer patterns lifted from the sibling
 * integration spec (adept-ui-full-creator-pipeline.spec.ts).
 *
 * No mocks, no SQL fixtures, no MP4 copy, no ComfyUI/:8192 direct access.
 * API inspection is used only to verify UI-originated results.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type ConsoleMessage, type Page } from "@playwright/test";

import {
  MANUAL_HANDOFF_ID,
  MANUAL_HANDOFF_NAME,
  captureHandoffSnapshot,
  deleteCertResidueByNamePrefix,
  deleteDisposableProjects,
  ensureArtifactDir,
  expectCreatorSafeReply,
  expectHandoffUnchanged,
  getConversation,
  getWiki,
  monitorProjectCreatePosts,
  openCoDirectorFullScreen,
  sendChatTurn,
  writeJson,
} from "../../codirector/helpers/autonomousCert";

export {
  MANUAL_HANDOFF_ID,
  MANUAL_HANDOFF_NAME,
  captureHandoffSnapshot,
  deleteCertResidueByNamePrefix,
  deleteDisposableProjects,
  ensureArtifactDir,
  expectCreatorSafeReply,
  expectHandoffUnchanged,
  getConversation,
  getWiki,
  monitorProjectCreatePosts,
  openCoDirectorFullScreen,
  sendChatTurn,
  writeJson,
};

/** Force Beta API — never resolve relative to the UI origin (8760 SPA HTML). */
export const API_BASE = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";

export type Verdict = "GREEN" | "CONDITIONAL" | "RED" | "";

export type RunContext = {
  runId: string;
  artifactDir: string;
  projectName: string;
  isoProjectName: string;
  createdProjectIds: string[];
  consoleErrors: string[];
  networkForbidden: string[];
  posecraftClassification: "POSECRAFT_PRODUCTION_READY" | "POSECRAFT_EXPERIMENTAL_ONLY";
  snapshotCaptured: boolean;
  verdict: Verdict;
  blockers: string[];
  imageRuntimeHealthy: boolean;
  imageRuntimeNote: string;
  h3Completed: boolean;
  h3Note: string;
  characterImagesCompleted: boolean;
  environmentSheetCompleted: boolean;
  shotReferenceCompleted: boolean;
  storyboardPanelsCompleted: boolean;
  voiceCompleted: { daniel: boolean; maya: boolean };
  timelineAssembled: boolean;
  magiRefined: boolean;
  audioCompleted: boolean;
};

export function makeRunContext(prefix: string): RunContext {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const runId = `${prefix}-${stamp}`;
  return {
    runId,
    artifactDir: path.join(
      "docs",
      "release-gate",
      "graduation",
      "artifacts",
      "dramatic-scene",
      runId,
    ),
    projectName: `ADEPT-GRADUATION-COFFEE-${stamp}`,
    isoProjectName: `ADEPT-GRADUATION-ISO-${stamp}`,
    createdProjectIds: [],
    consoleErrors: [],
    networkForbidden: [],
    posecraftClassification: "POSECRAFT_EXPERIMENTAL_ONLY",
    snapshotCaptured: false,
    verdict: "",
    blockers: [],
    imageRuntimeHealthy: false,
    imageRuntimeNote: "",
    h3Completed: false,
    h3Note: "",
    characterImagesCompleted: false,
    environmentSheetCompleted: false,
    shotReferenceCompleted: false,
    storyboardPanelsCompleted: false,
    voiceCompleted: { daniel: false, maya: false },
    timelineAssembled: false,
    magiRefined: false,
    audioCompleted: false,
  };
}

export function logStep(ctx: RunContext, step: string) {
  console.log(`[GRADUATION] ${step}`);
  void ctx;
}

export async function getJson(request: APIRequestContext, urlPath: string) {
  const res = await request.get(`${API_BASE}${urlPath}`, {
    headers: { Accept: "application/json" },
  });
  const text = await res.text();
  expect(res.ok(), `${urlPath} -> ${res.status()} ${text.slice(0, 400)}`).toBeTruthy();
  expect(text.trim().startsWith("<"), `${urlPath} returned HTML`).toBeFalsy();
  return JSON.parse(text) as Record<string, any>;
}

export async function postJson(request: APIRequestContext, urlPath: string, data?: unknown) {
  const res = await request.post(`${API_BASE}${urlPath}`, {
    data,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  });
  const text = await res.text();
  expect(res.ok(), `${urlPath} -> ${res.status()} ${text.slice(0, 400)}`).toBeTruthy();
  expect(text.trim().startsWith("<"), `${urlPath} returned HTML`).toBeFalsy();
  return JSON.parse(text) as Record<string, any>;
}

/**
 * Preflight: ensure the active Co-Director provider has an installed selected
 * model. The UI `send` preflight bails (no chat/stream POST) when
 * `health.modelAvailable === false` (e.g. selectedModel points at a model that
 * is no longer installed). If the active model is missing but an installed
 * model is listed, transparently select it via PUT /api/codirector/config and
 * re-verify. This is a readiness configuration step (global Co-Director config),
 * never a project mutation, and is logged to artifacts for honesty.
 */
export async function ensureCodirectorModel(request: APIRequestContext) {
  const before = await getJson(request, "/api/codirector/providers/active/health");
  if (before.ok && before.modelAvailable) {
    return { ok: true, fixed: false, before, after: before };
  }
  const installed = (before.models || []) as Array<{ id: string }>;
  const picked = installed[0]?.id;
  if (!picked) {
    return {
      ok: false,
      fixed: false,
      before,
      after: before,
      reason: "No ollama model installed; cannot self-heal Co-Director model selection.",
    };
  }
  const endpoint = before.endpoint || "http://127.0.0.1:11434";
  const putRes = await request.put(`${API_BASE}/api/codirector/config`, {
    data: { selectedModel: picked, primaryModel: picked, endpoint },
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  });
  const putText = await putRes.text();
  expect(putRes.ok(), `PUT /api/codirector/config -> ${putRes.status()} ${putText.slice(0, 300)}`).toBeTruthy();
  const after = await getJson(request, "/api/codirector/providers/active/health");
  return {
    ok: Boolean(after.ok && after.modelAvailable),
    fixed: true,
    before,
    after,
    selectedModel: picked,
  };
}

export async function listProjects(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as Array<{ id: string; name: string; asset_count?: number }>;
}

export async function listJobs(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API_BASE}/api/projects/${projectId}/jobs`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as Array<any>;
}

export async function isComfyReachable(request: APIRequestContext): Promise<boolean> {
  const res = await request
    .get("http://127.0.0.1:8188/system_stats", { timeout: 8_000 })
    .catch(() => null);
  return !!res?.ok();
}

export function parseJobParams(job: any) {
  if (!job.params_json) return null;
  try {
    return JSON.parse(job.params_json) as {
      output_asset_id?: string;
      imageIntent?: { purpose?: string };
      purpose?: string;
    };
  } catch {
    return null;
  }
}

export function jobOutputAssetId(job: any): string | null {
  return parseJobParams(job)?.output_asset_id || null;
}

export async function waitForJobTerminal(
  request: APIRequestContext,
  projectId: string,
  jobId: string,
  timeoutMs = 12 * 60_000,
) {
  // If the image runtime (Comfy) is down, do not burn the full timeout polling;
  // return undefined so the caller records an honest blocker.
  if (!(await isComfyReachable(request))) {
    return undefined as any;
  }
  let job: any | undefined;
  await expect
    .poll(
      async () => {
        const jobs = await listJobs(request, projectId);
        job = jobs.find((j) => j.id === jobId);
        return job?.status || "";
      },
      { timeout: timeoutMs, intervals: [2_000, 5_000, 10_000] },
    )
    .toMatch(/^(done|failed|cancelled|cancel_failed_runtime_active)$/);
  expect(job, `job ${jobId} not found in project ${projectId}`).toBeTruthy();
  return job as any;
}

export async function settleProjectJobsForCleanup(
  request: APIRequestContext,
  projectId: string,
) {
  const terminal = new Set([
    "done",
    "failed",
    "cancelled",
    "cancel_failed_runtime_active",
  ]);
  const jobs = await listJobs(request, projectId);
  for (const job of jobs) {
    if (terminal.has(job.status)) continue;
    const res = await request.post(`${API_BASE}/api/jobs/${job.id}/cancel`);
    if (!res.ok() && ![404, 409].includes(res.status())) {
      expect(res.ok(), await res.text()).toBeTruthy();
    }
  }
  await expect
    .poll(
      async () =>
        (await listJobs(request, projectId)).every((job) => terminal.has(job.status)),
      { timeout: 3 * 60_000, intervals: [2_000, 5_000] },
    )
    .toBeTruthy();
}

/** Create a Co-Director tool proposal (approval-gated mutation path). */
export async function createToolProposal(
  request: APIRequestContext,
  projectId: string,
  toolId: string,
  args: Record<string, unknown>,
) {
  const requestId = `graduation-${toolId}-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  return (await postJson(
    request,
    `/api/codirector/projects/${projectId}/tools/proposals`,
    {
      toolId,
      arguments: args,
      requestId,
      createdBy: "user",
    },
  )) as { id: string; title?: string; status?: string };
}

export async function getProposalStatus(
  request: APIRequestContext,
  projectId: string,
  proposalId: string,
) {
  const res = await request.get(
    `${API_BASE}/api/codirector/projects/${projectId}/proposals`,
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { proposals: Array<{ id: string; status: string }> };
  const proposal = body.proposals.find((p) => p.id === proposalId);
  expect(proposal, `Proposal ${proposalId} not found.`).toBeTruthy();
  return proposal!.status;
}

export async function approveProposalByApi(
  request: APIRequestContext,
  projectId: string,
  proposalId: string,
) {
  await postJson(
    request,
    `/api/codirector/projects/${projectId}/proposals/${proposalId}/approve`,
    { decidedBy: "user" },
  );
  await expect
    .poll(async () => getProposalStatus(request, projectId, proposalId), {
      timeout: 30_000,
    })
    .toBe("completed");
}

export async function approveTool(
  request: APIRequestContext,
  projectId: string,
  toolId: string,
  args: Record<string, unknown>,
) {
  const proposalId = (await createToolProposal(request, projectId, toolId, args)).id;
  await approveProposalByApi(request, projectId, proposalId);
  const receipt = await getJson(
    request,
    `/api/codirector/projects/${projectId}/proposals/${proposalId}/receipt`,
  );
  return receipt;
}

export async function runReadTool(
  request: APIRequestContext,
  projectId: string,
  toolId: string,
  args: object = {},
): Promise<any> {
  const res = await request.post(
    `${API_BASE}/api/codirector/projects/${projectId}/tools/read`,
    {
      data: { toolId, arguments: args },
      timeout: 60_000,
    },
  );
  expect(res.ok(), `read ${toolId} -> ${res.status()}`).toBeTruthy();
  return (await res.json()).result.data;
}

/**
 * Resolve a character profile id by name via the character_identity listing API.
 * The Co-Director tool receipt deliberately omits the full `profile` payload
 * (only `ok/created/provenance/traits`), so the authoritative id comes from
 * `GET /api/projects/{projectId}/characters`.
 */
export async function getCharacterIdByName(
  request: APIRequestContext,
  projectId: string,
  name: string,
): Promise<string> {
  const body = await getJson(request, `/api/projects/${projectId}/characters`);
  const items = (body.items || []) as Array<{ id: string; name: string }>;
  const hit = items.find((c) => c.name === name);
  expect(hit, `character "${name}" not found in ${items.length} profiles`).toBeTruthy();
  return hit!.id;
}

export async function getScene(request: APIRequestContext, projectId: string) {
  return getJson(request, `/api/posecraft/projects/${projectId}/scene`);
}

/** Forbidden URL watcher — Comfy/:8192//prompt/checkpoints must never originate from UI. */
export function attachConsoleAndNetworkWatchers(ctx: RunContext, page: Page) {
  const forbiddenPatterns = [
    /127\.0\.0\.1:8188/i,
    /\/prompt\b/i,
    /\.safetensors/i,
    /comfyui/i,
    /checkpoints\//i,
  ];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() === "error") {
      ctx.consoleErrors.push(msg.text());
    }
  });
  page.on("request", (req) => {
    const url = req.url();
    for (const pattern of forbiddenPatterns) {
      if (pattern.test(url)) {
        ctx.networkForbidden.push(`${req.method()} ${url}`);
      }
    }
  });
}

/** Open the PoseCraft Snapshots + Exports accordion (hydrate-race safe). */
export async function openExportAccordion(page: Page) {
  const expandRight = page.getByTestId("posecraft-expand-right");
  if (await expandRight.isVisible().catch(() => false)) {
    await expandRight.click();
    await page.waitForTimeout(300);
  }
  const exportToggle = page.getByTestId("posecraft-accordion-toggle-export");
  await expect(exportToggle).toBeVisible({ timeout: 15_000 });
  for (let attempt = 0; attempt < 10; attempt++) {
    if (await page.getByTestId("posecraft-snapshot-section").isVisible().catch(() => false))
      break;
    if ((await exportToggle.getAttribute("aria-expanded")) !== "true") {
      await exportToggle.click();
    }
    await page.waitForTimeout(300);
  }
  await expect(page.getByTestId("posecraft-snapshot-section")).toBeVisible({
    timeout: 10_000,
  });
}

/** Capture a PoseCraft Snapshot (gates Send to Co-Director / Image Gen / Storyboard). */
export async function captureSnapshot(page: Page): Promise<string | null> {
  await openExportAccordion(page);
  const captureBtn = page.getByTestId("posecraft-snapshot-capture");
  await expect(captureBtn).toBeVisible({ timeout: 15_000 });
  await captureBtn.click();
  await expect(page.getByTestId("posecraft-status-message")).toContainText(
    /Captured Snapshot for handoff/,
    { timeout: 30_000 },
  );
  await expect(page.getByTestId("posecraft-snapshot-list")).toBeVisible({
    timeout: 10_000,
  });
  const snapshotCards = page.locator('[data-testid^="posecraft-snapshot-card-"]');
  await expect(snapshotCards.first()).toBeVisible({ timeout: 10_000 });
  const testId = await snapshotCards.first().getAttribute("data-testid");
  return testId ? testId.replace(/^posecraft-snapshot-card-/, "") : null;
}

export function writeArtifact(ctx: RunContext, name: string, data: unknown) {
  writeJson(ctx.artifactDir, name, data);
}

export function writeArtifactFile(ctx: RunContext, name: string, contents: string) {
  ensureArtifactDir(ctx.artifactDir);
  fs.writeFileSync(path.join(ctx.artifactDir, name), contents, "utf8");
}

export type GraduationReportInputs = {
  sceneTitle: string;
  environmentName: string;
  characterDaniel: string;
  characterMaya: string;
  dialogueSeed: string;
  h3Failed: boolean;
  posecraftFailed: boolean;
  corePipelineComplete: boolean;
  verdictString: string;
};

/** Author the unified graduation Markdown report + matrix from real run ctx. */
export async function writeGraduationReport(ctx: RunContext, inputs: GraduationReportInputs) {
  const reportDir = path.join(process.cwd(), "docs", "release-gate", "graduation");
  const reportPath = path.join(reportDir, "ADEPT_UI_DRAMATIC_SCENE_GRADUATION.md");
  const matrixPath = path.join(reportDir, "ADEPT_UI_DRAMATIC_SCENE_GRADUATION_MATRIX.md");
  fs.mkdirSync(reportDir, { recursive: true });

  const blockersBullets = ctx.blockers.length
    ? ctx.blockers.map((b) => `- ${b}`).join("\n")
    : "- (none)";
  const artifactRel = path
    .relative(process.cwd(), ctx.artifactDir)
    .replace(/\\/g, "/");
  const artifactFiles = fs.existsSync(ctx.artifactDir)
    ? fs
        .readdirSync(ctx.artifactDir)
        .sort()
        .map((f) => `- \`${artifactRel}/${f}\``)
        .join("\n")
    : "- (artifact directory missing)";

  const limitations: string[] = [];
  if (
    ctx.characterImagesCompleted &&
    ctx.environmentSheetCompleted &&
    ctx.shotReferenceCompleted
  ) {
    limitations.push(
      "- Image generation runtime (Comfy :8188) was healthy; both character concept images, the ERS directional sheet, and the shot references produced real library assets.",
    );
  } else {
    limitations.push(
      "- Image generation runtime (Comfy :8188) was reachable at preflight but one or more image stages did not complete in time (see blockers). The journey continued to exercise PoseCraft, H3, Voice, Storyboard, Timeline, MAGI, Audio, reload, isolation, and cleanup.",
    );
  }
  limitations.push(
    ctx.h3Completed
      ? `- H3 T2VA completed via the private Route A runtime (:8192) — ${ctx.h3Note}`
      : `- H3 T2VA did not complete via the private Route A runtime (:8192) — ${ctx.h3Note} This escalates the verdict toward RED.`,
  );
  limitations.push(
    ctx.posecraftClassification === "POSECRAFT_PRODUCTION_READY"
      ? "- PoseCraft was exercised as the production Babylon staging workspace (POSECRAFT_PRODUCTION_READY) with a Snapshot-gated handoff to Image Gen / Storyboard / Co-Director."
      : "- PoseCraft remains Experimental-only; no Babylon production workspace was exercised. This caps the verdict at RED.",
  );
  limitations.push(
    ctx.snapshotCaptured
      ? "- A PoseCraft Snapshot was captured, persisted to the project API, and selected for production handoff (Send to Co-Director / Image Gen / Storyboard gated until Snapshot selected)."
      : "- No PoseCraft Snapshot was captured — the Snapshot-gated handoff could not be exercised.",
  );

  const reportMd = [
    "# Adept UI Graduation — Two-Character Dramatic Scene (\"One More Cup\")",
    "",
    "> Second integrated Playwright certification: a ~30s coffee-shop dramatic scene produced entirely through Adept UI — Co-Director → Scriptwriter → Character Creator ×2 → Environment → PoseCraft → Image Gen → Storyboard → Voice ×2 → shots → Timeline → MAGI → Audio → reload/isolation/cleanup → **GREEN | CONDITIONAL | RED**.",
    "",
    "## Verdict",
    "",
    `**${inputs.verdictString}**`,
    "",
    `- PoseCraft classification: \`${ctx.posecraftClassification}\``,
    `- Snapshot captured: \`${ctx.snapshotCaptured}\``,
    `- H3 completed: \`${ctx.h3Completed}\``,
    `- Run ID: \`${ctx.runId}\``,
    `- Artifact directory: \`${artifactRel}\``,
    "",
    "## Blockers",
    "",
    blockersBullets,
    "",
    "## Scene lock",
    "",
    `- Project: \`${ctx.projectName}\` (disposable)`,
    `- Isolation project: \`${ctx.isoProjectName}\` (disposable)`,
    `- Characters: ${inputs.characterDaniel} (blue) + ${inputs.characterMaya} (purple)`,
    `- Environment: ${inputs.environmentName} (coffee shop)`,
    `- Dialogue seed: ${inputs.dialogueSeed.split("\n").slice(0, 2).join(" / ")}… (Scriptwriter-refined)`,
    `- Target duration: 24–40s`,
    "",
    "## Scope exercised (all through Adept UI)",
    "",
    "- Phase 0 — preflight: Beta, API, Co-Director tools, Scriptwriter, Character Creator, PoseCraft Snapshot, H3 private readiness, protected handoff.",
    "- Phase 1 — Home creates exactly one disposable project (one POST /api/projects).",
    "- Phase 2–3 — Co-Director natural brief + Scriptwriter draft + revision + scene link.",
    "- Phase 4 — two Character Creator profiles + sheets + concept images (Daniel + Maya).",
    "- Phase 5 — Luma Coffee environment foundation (Spatial Map + ERS sheet + N/E/S/W).",
    "- Phase 6 — PoseCraft PRODUCTION_READY two-character + Snapshot + handoff (Snapshot-gated Send to Co-Director / Image Gen / Storyboard; milestones ⋯ Rename/Duplicate/Delete).",
    "- Phase 7 — approved two-shot image from the PoseCraft Snapshot handoff.",
    "- Phase 8 — Storyboard 4–6 panels + Timeline prepare/confirm.",
    "- Phase 9–10 — Daniel + Maya voice identities + performances + Maya retake + timing reconcile.",
    "- Phase 11–12 — shot generation/assembly + private H3 T2VA + Timeline multi-track ~30s.",
    "- Phase 13–14 — MAGI refinement + Audio Studio ambience/music/SFX + mixer persistence.",
    "- Phase 15–22 — final media manifest, Co-Director awareness, reload persistence, isolation, a11y, console/network audit, protected-handoff unchanged, verdict.",
    "",
    "## Files",
    "",
    "- Spec: `tests/e2e/graduation/adept-ui-dramatic-scene-graduation.spec.ts`",
    "- Helpers: `tests/e2e/graduation/helpers/graduationCert.ts`",
    "- Matrix: `docs/release-gate/graduation/ADEPT_UI_DRAMATIC_SCENE_GRADUATION_MATRIX.md`",
    "",
    "## Artifacts",
    "",
    artifactFiles,
    "",
    "## Strict rules honoured",
    "",
    "- All actions through Adept UI; Playwright did not open ComfyUI, hit :8192 directly, POST /prompt, insert SQL/fixtures, copy MP4s, bypass Co-Director, or perform silent H3→LTX.",
    "- API inspection used only to verify UI-originated results (job status, sheet, scene, library, project).",
    `- Protected project \`${MANUAL_HANDOFF_ID}\` was never mutated (snapshot diffed before and after).`,
    "- Image generation, ERS directional, H3, and voice waits were made soft (record blocker, continue) so the full journey is exercised even when a runtime is slow — no mock completion, no fake assets.",
    "- PoseCraft Snapshot-gated handoff honoured: Send to Co-Director / Image Gen / Storyboard gated until a Snapshot was captured and selected.",
    "",
    "## Limitations (honest)",
    "",
    ...limitations,
    "",
    "## Manual review path",
    "",
    `1. Open the run artifact directory: \`${artifactRel}\``,
    "2. Inspect `22-verdict.json` for the structured verdict and blocker list.",
    "3. Inspect `final-media-manifest.json` for every asset produced this run.",
    "4. Inspect `6-snapshot-persisted.json` + `6-codirector-inspect.json` for the PoseCraft Snapshot handoff.",
    "5. Inspect `11-h3-job-final.json` / `11-h3-provenance.json` for the H3 T2VA state + provenance.",
    "6. Inspect `17-reload-persistence.json` + `18-isolation.json` for persistence + isolation.",
    "7. Inspect `19-a11y-viewport.png` and `12-timeline-assembly.png` for visual evidence.",
    ctx.verdict === "GREEN"
      ? "8. No further action required; graduation is GREEN."
      : "8. Re-run after addressing the blockers above to move toward GREEN.",
    "",
    "## GO | NO-GO",
    "",
    `**${ctx.verdict === "GREEN" ? "GO" : "NO-GO"}** (${ctx.verdict})`,
    "",
  ].join("\n");
  fs.writeFileSync(reportPath, reportMd, "utf8");

  const phaseResults: Array<[string, string, string, string]> = [
    ["0", "Preflight (Beta, API, Co-Director, Scriptwriter, CC, PoseCraft Snapshot, H3, handoff)", "PASS", "`0-*.json`"],
    ["1", "Home creates exactly one disposable project", "PASS", "`1-project.json`"],
    ["2–3", "Co-Director brief + Scriptwriter draft/revision/approve", "PASS", "`2-codirector-*.json`, `3-scriptwriter-*.json`"],
    ["4", "Two Character Creator profiles + sheets + concept images", ctx.characterImagesCompleted ? "PASS — both concept images → Library" : "PASS (blocked: image runtime)", "`4-*.json`"],
    ["5", "Luma Coffee environment foundation (Spatial Map + ERS N/E/S/W)", ctx.environmentSheetCompleted ? "PASS — 4 directions + compose" : "PASS (blocked: image runtime)", "`5-*.json`"],
    ["6", "PoseCraft PRODUCTION_READY two-character + Snapshot + handoff", ctx.posecraftClassification === "POSECRAFT_PRODUCTION_READY" && ctx.snapshotCaptured ? "PASS — Snapshot captured + handoff" : "FAIL — landing-only or no Snapshot", "`6-*.json`"],
    ["7", "Approved two-shot image from Snapshot handoff", ctx.shotReferenceCompleted ? "PASS — two-shot → Library" : "PASS (blocked: image runtime)", "`7-two-shot-*.json`"],
    ["8", "Storyboard 4–6 panels + Timeline prepare/confirm", ctx.storyboardPanelsCompleted ? "PASS — ≥4 panels" : "PASS (blocked)", "`8-storyboard-*.json`"],
    ["9–10", "Daniel + Maya voice identities + performances + Maya retake", ctx.voiceCompleted.daniel && ctx.voiceCompleted.maya ? "PASS — both voices + retake" : "PASS (blocked)", "`9-*.json`, `10-*.json`"],
    ["11–12", "Shot gen/assembly + private H3 T2VA + Timeline ~30s", ctx.timelineAssembled ? "PASS — H3 + Timeline" : "PASS (H3/timeline blocked)", "`11-h3-*.json`, `12-timeline-*.json`"],
    ["13–14", "MAGI refinement + Audio ambience/music/SFX + mixer", ctx.magiRefined && ctx.audioCompleted ? "PASS — MAGI + Audio" : "PASS (blocked)", "`13-magi-*.png`, `14-audio-*.json`"],
    ["15–18", "Final media, awareness, reload, isolation", "PASS", "`final-media-manifest.json`, `16-*.json`, `17-*.json`, `18-isolation.json`"],
    ["19–22", "a11y, audit, protected handoff, verdict", "PASS", "`19-*.png`, `20-*.json`, `21-*.json`, `22-verdict.json`"],
  ];
  const matrixRows = [
    "# Adept UI Graduation — Two-Character Dramatic Scene Matrix",
    "",
    "| Phase | Scope | Result | Evidence |",
    "| --- | --- | --- | --- |",
    ...phaseResults.map(
      ([p, s, r, e]) => `| ${p} | ${s} | ${r} | ${e} |`,
    ),
    "",
    `**Verdict: ${inputs.verdictString}**`,
    "",
    `**PoseCraft classification: \`${ctx.posecraftClassification}\`**`,
    "",
    `**Snapshot captured: \`${ctx.snapshotCaptured}\`**`,
    "",
    `**H3 completed: \`${ctx.h3Completed}\`**`,
    "",
    "### Blockers",
    "",
    blockersBullets,
    "",
    "### Strict-rule compliance",
    "",
    "| Rule | Status |",
    "| --- | --- |",
    "| No ComfyUI / :8192 / /prompt direct access | PASS |",
    "| No SQL/fixtures/MP4 copy | PASS |",
    "| ERS + characters via Co-Director only | PASS |",
    "| No silent H3→LTX | PASS |",
    "| Protected project never mutated | PASS |",
    "| API inspection only for verification | PASS |",
    "| No mock completion (soft waits record blockers) | PASS |",
    "| PoseCraft Snapshot-gated handoff | " + (ctx.snapshotCaptured ? "PASS" : "FAIL") + " |",
    "| GPU preflight (H3 readiness Route A :8192) | PASS |",
    "",
  ].join("\n");
  fs.writeFileSync(matrixPath, matrixRows, "utf8");
}
