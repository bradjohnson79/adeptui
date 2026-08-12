/**
 * Final Timeline Two-Batch Playwright Certification
 *
 * Locked engine: MiniMax H3 33B via shared provider-agnostic Timeline generation workflow.
 * Exactly 2 batches × (1 image planning anchor + 1 prompt) → 2 real MiniMax clips on Timeline.
 *
 * Run (Beta only):
 *   npm run test:e2e:beta -- tests/e2e/timeline/timeline-two-batch-final-certification.spec.ts --project=chromium --retries=0 --workers=1
 */
import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import {
  API,
  BETA_TARGET,
  createTempProject,
  deleteProject,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

const PROTECTED = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const GENERATOR_ID = "minimax-h3-local";
const RUN_ID = new Date().toISOString().replace(/[:.]/g, "-");
const ARTIFACT_DIR = path.resolve(
  process.cwd(),
  "docs",
  "release-gate",
  "timeline",
  "artifacts",
  "timeline-two-batch-final-certification",
  RUN_ID,
);

const PROMPT_1 =
  "A glowing glass perfume bottle on dark velvet, slow cinematic push-in, subtle condensation, controlled rim light.";
const PROMPT_2 =
  "Same bottle from a low angle, gentle orbit, soft golden highlights, shallow depth of field, studio haze.";

const PNG_A = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mP8z8BQz0AEYBxVSF+FAP5IDveKW/F2AAAAAElFTkSuQmCC",
  "base64",
);
const PNG_B = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mNk+M9Qz0AEYBxVSF+FAAhKDveksH63AAAAAElFTkSuQmCC",
  "base64",
);

function writeJson(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

async function ensureScene(request: APIRequestContext, projectId: string): Promise<string> {
  const list = await request.get(`${API}/api/projects/${projectId}/scenes`);
  const body = await list.json();
  const scenes = body.scenes || body || [];
  if (Array.isArray(scenes) && scenes[0]?.id) return String(scenes[0].id);
  const created = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { title: "Two-Batch Scene", prompt: PROMPT_1, duration_sec: 5 },
  });
  const c = await created.json();
  return String(c.id || c.scene?.id);
}

async function uploadImage(
  request: APIRequestContext,
  projectId: string,
  name: string,
  buffer: Buffer,
): Promise<string> {
  const upload = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name, mimeType: "image/png", buffer },
      kind: "image",
      tag: name.replace(/\.png$/i, ""),
    },
  });
  expect(upload.ok(), `upload ${name}`).toBeTruthy();
  const body = await upload.json();
  const id = body.id || body.asset?.id || body.assetId;
  expect(id, `asset id for ${name}`).toBeTruthy();
  return String(id);
}

async function loadMaster(request: APIRequestContext, projectId: string, sceneId: string) {
  let lastErr: unknown = null;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    try {
      const res = await request.get(
        `${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/master`,
        { timeout: 30_000 },
      );
      if (!res.ok()) {
        lastErr = new Error(`master HTTP ${res.status()}`);
        await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
        continue;
      }
      return res.json();
    } catch (err) {
      lastErr = err;
      await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

async function configureBatchViaApi(
  request: APIRequestContext,
  projectId: string,
  sceneId: string,
  batchId: string,
  opts: { label: string; prompt: string; imageAssetId: string },
) {
  const { label, prompt, imageAssetId } = opts;
  const res = await request.patch(
    `${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/batches/${batchId}`,
    {
      data: {
        label,
        generatorId: GENERATOR_ID,
        plannedDuration: 5,
        promptSegments: [
          {
            id: `ps_${batchId}`,
            start: 0,
            length: 5,
            text: prompt,
            role: "primary",
            strength: 1,
            anchorIds: [],
            executionStrategy: "compiled",
            versionId: `psv_${batchId}`,
          },
        ],
        sourceAnchors: [
          {
            id: `anc_${batchId}`,
            kind: "image",
            assetId: imageAssetId,
            label: "Start",
            atTime: 0,
            strength: 1,
          },
        ],
      },
    },
  );
  expect(res.ok(), `patch batch ${batchId}`).toBeTruthy();
  return res.json();
}

async function openTimeline(page: Page, projectId: string, sceneId: string) {
  await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${encodeURIComponent(sceneId)}`);
  await expect(page.getByTestId("timeline-track-board")).toBeVisible({ timeout: 60_000 });
}

async function waitBatchApproved(
  request: APIRequestContext,
  projectId: string,
  sceneId: string,
  batchId: string,
  timeoutMs = 25 * 60_000,
) {
  let last: any = null;
  await expect
    .poll(
      async () => {
        const ws = await loadMaster(request, projectId, sceneId);
        const batch = (ws.master?.batchBlocks || []).find((b: any) => b.id === batchId);
        last = batch;
        if (!batch) return "missing";
        if (batch.status === "Failed") return `failed:${batch.generationJobs?.slice(-1)?.[0]?.error || ""}`;
        if (batch.status === "Approved" && batch.approvedClip?.assetId) return "approved";
        return `${batch.status}`;
      },
      { timeout: timeoutMs, intervals: [5_000, 10_000, 15_000] },
    )
    .toBe("approved");
  return last;
}

test.beforeEach(async ({ page, request }) => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 / npm run test:e2e:beta for live MiniMax certification.");
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @timeline Timeline Two-Batch Final Certification", () => {
  test("two MiniMax H3 batches → two Timeline clips → reload lineage", async ({ page, request }) => {
    test.setTimeout(60 * 60_000);

    // Phase 1 — MiniMax readiness (infrastructure hard stop)
    const readyRes = await request.get(`${API}/api/minimax-h3/readiness`);
    const ready = readyRes.ok() ? await readyRes.json() : { ok: false, ready: false };
    writeJson("01-minimax-readiness.json", ready);
    if (!ready.ready && !ready.ok) {
      writeJson("VERDICT.json", {
        verdict: "NO-GO — TIMELINE TWO-BATCH PLAYWRIGHT CERTIFICATION FAILED",
        reason: "MiniMax H3 runtime not ready — infrastructure NO-GO (no fallback)",
        ready,
      });
      throw new Error(
        `INFRASTRUCTURE NO-GO: MiniMax H3 not ready — ${ready.creatorStatus || ready.message || "offline"}`,
      );
    }

    const project = await createTempProject(request, `Timeline Two-Batch Cert ${Date.now()}`);
    const projectId = project.id;
    expect(projectId).not.toBe(PROTECTED);
    writeJson("02-project.json", { projectId, name: project.name });

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    try {
      const sceneId = await ensureScene(request, projectId);
      writeJson("03-scene.json", { sceneId });

      // Phase 3 — two distinct Library images
      const image1 = await uploadImage(request, projectId, "batch1-anchor.png", PNG_A);
      const image2 = await uploadImage(request, projectId, "batch2-anchor.png", PNG_B);
      expect(image1).not.toBe(image2);
      writeJson("04-images.json", { image1, image2 });

      // Ensure two batches + configure BEFORE opening Timeline UI (avoids stale UI COW overwrite).
      let ws = await loadMaster(request, projectId, sceneId);
      let batches = ws.master?.batchBlocks || [];
      while (batches.length < 2) {
        const add = await request.post(
          `${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/batches`,
          { data: { plannedDuration: 5, generatorId: GENERATOR_ID } },
        );
        expect(add.ok()).toBeTruthy();
        ws = await loadMaster(request, projectId, sceneId);
        batches = ws.master?.batchBlocks || [];
      }
      const batch1 = [...batches].sort((a: any, b: any) => a.order - b.order)[0];
      const batch2 = [...batches].sort((a: any, b: any) => a.order - b.order)[1];

      const cfg1 = await configureBatchViaApi(request, projectId, sceneId, batch1.id, {
        label: "Batch 1",
        prompt: PROMPT_1,
        imageAssetId: image1,
      });
      const cfg2 = await configureBatchViaApi(request, projectId, sceneId, batch2.id, {
        label: "Batch 2",
        prompt: PROMPT_2,
        imageAssetId: image2,
      });
      writeJson("04b-configure.json", { cfg1, cfg2 });

      // Phase 5 — isolation asserts (API truth before UI)
      ws = await loadMaster(request, projectId, sceneId);
      const b1 = (ws.master.batchBlocks as any[]).find((b) => b.id === batch1.id)!;
      const b2 = (ws.master.batchBlocks as any[]).find((b) => b.id === batch2.id)!;
      expect(b1.generatorId).toBe(GENERATOR_ID);
      expect(b2.generatorId).toBe(GENERATOR_ID);
      expect(b1.promptSegments[0].text).toContain("perfume bottle");
      expect(b2.promptSegments[0].text).toContain("low angle");
      expect(b1.sourceAnchors[0].assetId).toBe(image1);
      expect(b2.sourceAnchors[0].assetId).toBe(image2);
      expect(b1.sourceAnchors[0].assetId).not.toBe(b2.sourceAnchors[0].assetId);
      writeJson("05-isolation.json", { batch1: b1, batch2: b2 });

      await openTimeline(page, projectId, sceneId);

      // UI surface check — generator / prompt controls present when batch selected
      await page.getByTestId("timeline-batch-lane").getByTestId(`timeline-batch-${batch1.id}`).click();
      await expect(page.getByTestId("timeline-batch-generator")).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("timeline-batch-prompt")).toBeVisible();
      await expect(page.getByTestId("timeline-batch-start-image")).toBeVisible();
      await expect(page.getByTestId("timeline-batch-generator")).toHaveValue(GENERATOR_ID);

      // Phase 6–7 — sequential Gen Batch via Timeline UI; wait real MiniMax completions
      const genResponses: any[] = [];
      for (const batch of [batch1, batch2]) {
        await page.getByTestId("timeline-batch-lane").getByTestId(`timeline-batch-${batch.id}`).click();
        const genWait = page.waitForResponse(
          (r) =>
            r.url().includes(`/batches/${batch.id}/generate`) && r.request().method() === "POST",
          { timeout: 120_000 },
        );
        const genBtn = page.getByTestId("timeline-gen-batch");
        await expect(genBtn).toBeVisible({ timeout: 15_000 });
        await genBtn.click();
        const genRes = await genWait;
        const genBody = await genRes.json();
        genResponses.push(genBody);
        writeJson(`06-generate-${batch.id}.json`, genBody);
        expect(genBody.ok, JSON.stringify(genBody)).toBeTruthy();
        expect(genBody.generatorId).toBe(GENERATOR_ID);
        expect(genBody.queueJobId || genBody.internalJobId).toBeTruthy();
        expect(genBody.apiUsed).toBe(false);
        expect(genBody.normalizedRequest?.generatorId).toBe(GENERATOR_ID);
        expect(String(genBody.normalizedRequest?.generatorId || "")).not.toMatch(/ltx|seedance|kling/i);

        const approved = await waitBatchApproved(request, projectId, sceneId, batch.id);
        writeJson(`07-approved-${batch.id}.json`, approved);
        expect(approved.approvedClip.assetId).toBeTruthy();
        const lineage = (approved.references || []).find(
          (r: any) => r.kind === "timelineGenerationLineage",
        );
        expect(lineage?.generatorId).toBe(GENERATOR_ID);
        expect(lineage?.ltxUsed ?? false).toBeFalsy();
      }

      // Phase 8 — Timeline shape [Batch1][Batch2]
      const finalWs = await loadMaster(request, projectId, sceneId);
      const ordered = [...(finalWs.master.batchBlocks || [])].sort(
        (a: any, b: any) => a.order - b.order,
      );
      expect(ordered[0].approvedClip.assetId).toBeTruthy();
      expect(ordered[1].approvedClip.assetId).toBeTruthy();
      expect(ordered[0].approvedClip.assetId).not.toBe(ordered[1].approvedClip.assetId);

      let videoClips: any[] = [];
      const sceneRes = await request.get(`${API}/api/projects/${projectId}/scenes/${sceneId}`);
      const sceneBody = sceneRes.ok() ? await sceneRes.json() : {};
      const directorRaw = sceneBody.director_json ?? sceneBody.directorJson ?? sceneBody.director;
      if (directorRaw) {
        const dj = typeof directorRaw === "string" ? JSON.parse(directorRaw) : directorRaw;
        videoClips = dj.video_clips || [];
        writeJson("08-director.json", { video_clips: videoClips, media_mode: dj.media_mode });
      } else {
        const scenesList = await request.get(`${API}/api/projects/${projectId}/scenes`);
        const scenesJson = await scenesList.json();
        const sceneRow = (scenesJson.scenes || scenesJson || []).find((s: any) => s.id === sceneId);
        if (sceneRow?.director_json) {
          const dj =
            typeof sceneRow.director_json === "string"
              ? JSON.parse(sceneRow.director_json)
              : sceneRow.director_json;
          videoClips = dj.video_clips || [];
          writeJson("08-director.json", { video_clips: videoClips, media_mode: dj.media_mode });
        } else {
          writeJson("08-scene-debug.json", { sceneBody, scenesJson });
        }
      }

      const managed = (videoClips || [])
        .filter((c: any) => String(c.id || "").startsWith("bbclip_"))
        .sort((a: any, b: any) => a.start - b.start);
      expect(managed.length, "expected two managed Timeline video clips").toBe(2);
      expect(managed[0].asset_id).toBe(ordered[0].approvedClip.assetId);
      expect(managed[1].asset_id).toBe(ordered[1].approvedClip.assetId);
      expect(managed[0].start).toBeLessThan(managed[1].start);

      // Phase 9 — reload lineage
      await page.reload();
      await openTimeline(page, projectId, sceneId);
      const reloadWs = await loadMaster(request, projectId, sceneId);
      writeJson("09-reload-master.json", reloadWs.master);
      const rb = [...(reloadWs.master.batchBlocks || [])].sort((a: any, b: any) => a.order - b.order);
      expect(rb[0].status).toBe("Approved");
      expect(rb[1].status).toBe("Approved");
      expect(rb[0].approvedClip.assetId).toBe(ordered[0].approvedClip.assetId);
      expect(rb[1].approvedClip.assetId).toBe(ordered[1].approvedClip.assetId);

      // Phase 10 — console/network audit (no silent LTX)
      writeJson("10-console-errors.json", { consoleErrors });
      for (const g of genResponses) {
        expect(g.apiUsed).toBe(false);
        expect(String(g.generatorId)).toBe(GENERATOR_ID);
      }

      writeJson("11-lineage-summary.json", {
        projectId,
        sceneId,
        generatorId: GENERATOR_ID,
        model: "MiniMax H3 33B / Experimental Private Profile",
        fallbackAllowed: false,
        batches: rb.map((b: any) => ({
          batchBlockId: b.id,
          label: b.label,
          executionSnapshotId: b.approvedClip?.executionSnapshotId,
          outputAssetId: b.approvedClip?.assetId,
          inputImageAssetId: b.sourceAnchors?.[0]?.assetId,
          generatorId: b.generatorId,
          jobs: b.generationJobs,
          lineage: (b.references || []).find((r: any) => r.kind === "timelineGenerationLineage"),
        })),
        videoClips: managed,
      });

      writeJson("VERDICT.json", {
        verdict: "GO — TIMELINE TWO-BATCH PLAYWRIGHT CERTIFICATION PASSED",
        architectureStatement:
          "The final two-batch certification rendered with MiniMax H3 33B through the shared provider-agnostic Timeline generation workflow.",
        artifactDir: ARTIFACT_DIR,
      });
    } finally {
      await deleteProject(request, projectId);
    }
  });
});
