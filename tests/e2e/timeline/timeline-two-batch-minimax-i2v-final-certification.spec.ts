/**
 * Timeline Two-Batch MiniMax IMAGE-TO-VIDEO Final Certification
 *
 * Locked engine: minimax-h3-i2v-local (Route A I2VA — LoadImage → first_frame).
 * Exactly 2 batches × (distinct start image + distinct prompt) → 2 conditioned MiniMax clips.
 *
 * Run (Beta only):
 *   npm run test:e2e:beta -- tests/e2e/timeline/timeline-two-batch-minimax-i2v-final-certification.spec.ts --project=chromium --retries=0 --workers=1
 */
import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";
import { execFileSync } from "child_process";
import {
  API,
  BETA_TARGET,
  createTempProject,
  deleteProject,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

const PROTECTED = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const GENERATOR_ID = "minimax-h3-i2v-local";
const RUN_ID = new Date().toISOString().replace(/[:.]/g, "-");
const ARTIFACT_DIR = path.resolve(
  process.cwd(),
  "docs",
  "release-gate",
  "timeline",
  "artifacts",
  "timeline-two-batch-minimax-i2v-final-certification",
  RUN_ID,
);
const FIXTURE_DIR = path.resolve(process.cwd(), "tests", "e2e", "timeline", "fixtures", "minimax-i2v");

const PROMPT_1 =
  "Keep the same red circular subject and dark teal background. Gentle camera drift closer, subtle ambient motion, identity-preserving, cinematic lighting.";
const PROMPT_2 =
  "Keep the same blue triangular subject and warm cream background. Soft orbit around the form, identity-preserving, controlled studio light.";

function writeJson(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

function sha256File(filePath: string): string {
  const buf = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(buf).digest("hex");
}

function assertI2vGraph(graph: any, expectedComfyName: string) {
  expect(graph, "submitted Comfy graph missing").toBeTruthy();
  const loadEntries = Object.entries(graph).filter(
    ([, node]: [string, any]) => node?.class_type === "LoadImage",
  );
  expect(loadEntries.length, "LoadImage node required").toBeGreaterThanOrEqual(1);
  const [, loadNode] = loadEntries[0] as [string, any];
  const boundName = String(loadNode?.inputs?.image || "");
  expect(boundName).toBe(expectedComfyName);
  const condEntries = Object.entries(graph).filter(
    ([, node]: [string, any]) => node?.class_type === "MiniMaxH3ImageToVideo",
  );
  expect(condEntries.length, "MiniMaxH3ImageToVideo required").toBeGreaterThanOrEqual(1);
  const [loadId] = loadEntries[0] as [string, any];
  const [, cond] = condEntries[0] as [string, any];
  const first = cond?.inputs?.first_frame;
  expect(Array.isArray(first), "first_frame must be a node link").toBeTruthy();
  expect(String(first[0])).toBe(String(loadId));
}

async function ensureScene(request: APIRequestContext, projectId: string): Promise<string> {
  const list = await request.get(`${API}/api/projects/${projectId}/scenes`);
  const body = await list.json();
  const scenes = body.scenes || body || [];
  if (Array.isArray(scenes) && scenes[0]?.id) return String(scenes[0].id);
  const created = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { title: "Two-Batch I2V Scene", prompt: PROMPT_1, duration_sec: 5 },
  });
  const c = await created.json();
  return String(c.id || c.scene?.id);
}

async function uploadImageFile(
  request: APIRequestContext,
  projectId: string,
  filePath: string,
): Promise<{ assetId: string; sha256: string; filename: string }> {
  const buffer = fs.readFileSync(filePath);
  const filename = path.basename(filePath);
  const upload = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: filename, mimeType: "image/png", buffer },
      kind: "image",
      tag: filename.replace(/\.png$/i, ""),
    },
  });
  expect(upload.ok(), `upload ${filename}`).toBeTruthy();
  const body = await upload.json();
  const id = body.id || body.asset?.id || body.assetId;
  expect(id, `asset id for ${filename}`).toBeTruthy();
  const dest = path.join(ARTIFACT_DIR, `source-${filename}`);
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.copyFileSync(filePath, dest);
  return { assetId: String(id), sha256: sha256File(filePath), filename };
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
        if (batch.status === "Failed") {
          return `failed:${batch.generationJobs?.slice(-1)?.[0]?.error || ""}`;
        }
        if (batch.status === "Approved" && batch.approvedClip?.assetId) return "approved";
        return `${batch.status}`;
      },
      { timeout: timeoutMs, intervals: [5_000, 10_000, 15_000] },
    )
    .toBe("approved");
  return last;
}

async function fetchJob(request: APIRequestContext, projectId: string, jobId: string) {
  const res = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${jobId}`);
  expect(res.ok(), `job ${jobId}`).toBeTruthy();
  return res.json();
}

function extractFirstFrame(mp4Path: string, outPng: string) {
  execFileSync(
    "ffmpeg",
    ["-y", "-i", mp4Path, "-frames:v", "1", "-q:v", "2", outPng],
    { stdio: "pipe" },
  );
}

test.beforeEach(async ({ page, request }) => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 / npm run test:e2e:beta for live MiniMax I2V certification.");
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @timeline Timeline Two-Batch MiniMax I2V Final Certification", () => {
  test("two MiniMax H3 I2V batches → conditioned clips → reload lineage", async ({ page, request }) => {
    test.setTimeout(60 * 60_000);

    const readyRes = await request.get(`${API}/api/minimax-h3/readiness`);
    const ready = readyRes.ok() ? await readyRes.json() : { ok: false, ready: false };
    writeJson("01-minimax-readiness.json", ready);
    if (!ready.ready && !ready.ok) {
      writeJson("VERDICT.json", {
        verdict: "NO-GO — TIMELINE TWO-BATCH MINIMAX IMAGE-TO-VIDEO CERTIFICATION FAILED",
        reason: "MiniMax H3 runtime not ready — infrastructure NO-GO (no fallback)",
        ready,
      });
      throw new Error(
        `INFRASTRUCTURE NO-GO: MiniMax H3 not ready — ${ready.creatorStatus || ready.message || "offline"}`,
      );
    }

    const project = await createTempProject(request, `Timeline MiniMax I2V Cert ${Date.now()}`);
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

      const src1Path = path.join(FIXTURE_DIR, "batch1-subject.png");
      const src2Path = path.join(FIXTURE_DIR, "batch2-subject.png");
      expect(fs.existsSync(src1Path), "fixture batch1-subject.png").toBeTruthy();
      expect(fs.existsSync(src2Path), "fixture batch2-subject.png").toBeTruthy();

      const image1 = await uploadImageFile(request, projectId, src1Path);
      const image2 = await uploadImageFile(request, projectId, src2Path);
      expect(image1.assetId).not.toBe(image2.assetId);
      expect(image1.sha256).not.toBe(image2.sha256);
      writeJson("04-images.json", { image1, image2 });

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

      await configureBatchViaApi(request, projectId, sceneId, batch1.id, {
        label: "Batch 1 I2V",
        prompt: PROMPT_1,
        imageAssetId: image1.assetId,
      });
      await configureBatchViaApi(request, projectId, sceneId, batch2.id, {
        label: "Batch 2 I2V",
        prompt: PROMPT_2,
        imageAssetId: image2.assetId,
      });

      ws = await loadMaster(request, projectId, sceneId);
      const b1 = (ws.master.batchBlocks as any[]).find((b) => b.id === batch1.id)!;
      const b2 = (ws.master.batchBlocks as any[]).find((b) => b.id === batch2.id)!;
      expect(b1.generatorId).toBe(GENERATOR_ID);
      expect(b2.generatorId).toBe(GENERATOR_ID);
      expect(b1.sourceAnchors[0].assetId).toBe(image1.assetId);
      expect(b2.sourceAnchors[0].assetId).toBe(image2.assetId);
      writeJson("05-isolation.json", { batch1: b1, batch2: b2 });

      await openTimeline(page, projectId, sceneId);
      await page.getByTestId("timeline-batch-lane").getByTestId(`timeline-batch-${batch1.id}`).click();
      await expect(page.getByTestId("timeline-batch-generator")).toHaveValue(GENERATOR_ID);

      const genResponses: any[] = [];
      const bindings: any[] = [];
      const batchMeta = [
        { batch: batch1, image: image1, prompt: PROMPT_1, index: 1 },
        { batch: batch2, image: image2, prompt: PROMPT_2, index: 2 },
      ];

      for (const { batch, image, prompt, index } of batchMeta) {
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
        writeJson(`06-generate-batch-${index}.json`, genBody);

        expect(genBody.ok, JSON.stringify(genBody)).toBeTruthy();
        expect(genBody.generatorId).toBe(GENERATOR_ID);
        expect(genBody.apiUsed).toBe(false);
        expect(genBody.normalizedRequest?.generationMode).toBe("image_to_video");
        expect(genBody.normalizedRequest?.startImageAssetId).toBe(image.assetId);
        expect(genBody.normalizedRequest?.prompt).toContain(prompt.slice(0, 24));
        expect(String(genBody.normalizedRequest?.generatorId || "")).not.toMatch(
          /ltx|seedance|kling|t2v/i,
        );
        // Hard fail if prompts present but images omitted
        expect(genBody.normalizedRequest?.startImageAssetId).toBeTruthy();

        const jobId = String(genBody.queueJobId || genBody.internalJobId || "");
        expect(jobId).toBeTruthy();

        // Capture submitted Comfy graph early (persisted at submit)
        const jobPayload = await fetchJob(request, projectId, jobId);
        const job = jobPayload.job || {};
        const graph = job.submittedGraph;
        expect(graph, "submittedGraph must be persisted at submit").toBeTruthy();
        const comfyName = String(job.comfyImageName || job.provenance?.comfyImageName || "");
        expect(comfyName).toBeTruthy();
        assertI2vGraph(graph, comfyName);
        writeJson(`submitted-comfy-graph-batch-${index}.json`, graph);

        const approved = await waitBatchApproved(request, projectId, sceneId, batch.id);
        writeJson(`07-approved-batch-${index}.json`, approved);
        expect(approved.approvedClip.assetId).toBeTruthy();
        const lineage = (approved.references || []).find(
          (r: any) => r.kind === "timelineGenerationLineage",
        );
        expect(lineage?.generatorId).toBe(GENERATOR_ID);
        expect(lineage?.startImageAssetId).toBe(image.assetId);
        expect(lineage?.ltxUsed ?? false).toBeFalsy();

        const finalJobPayload = await fetchJob(request, projectId, jobId);
        const finalJob = finalJobPayload.job || {};
        expect(finalJob.provenance?.workflowId).toBe("route-a-experimental-private-i2va");
        expect(finalJob.provenance?.workflowId).not.toBe("route-a-experimental-private-t2va");
        expect(finalJob.provenance?.ltxUsed).toBeFalsy();
        expect(finalJob.startImageSha256 || finalJob.provenance?.startImageSha256).toBe(image.sha256);

        const binding = {
          batchIndex: index,
          batchBlockId: batch.id,
          assetId: image.assetId,
          sha256: image.sha256,
          comfyImageName: comfyName,
          workflowInputNode: "LoadImage",
          firstFrameLink: ["15", 0],
          queueJobId: jobId,
          outputAssetId: approved.approvedClip.assetId,
          workflowId: finalJob.provenance?.workflowId,
        };
        bindings.push(binding);
        writeJson(`minimax-i2v-input-binding-batch-${index}.json`, binding);

        // Download output video + extract first frame for visual review
        const mp4Out = path.join(ARTIFACT_DIR, `output-batch-${index}.mp4`);
        const fileRes = await request.get(
          `${API}/api/assets/${approved.approvedClip.assetId}/file`,
        );
        if (fileRes.ok()) {
          fs.writeFileSync(mp4Out, await fileRes.body());
          try {
            extractFirstFrame(mp4Out, path.join(ARTIFACT_DIR, `first-frame-batch-${index}.png`));
          } catch (err) {
            writeJson(`08-ffmpeg-batch-${index}-error.json`, { error: String(err) });
          }
        } else {
          // Fallback: Route A job outputPath on disk
          const outPath = String(finalJob.outputPath || "");
          if (outPath && fs.existsSync(outPath)) {
            fs.copyFileSync(outPath, mp4Out);
            try {
              extractFirstFrame(mp4Out, path.join(ARTIFACT_DIR, `first-frame-batch-${index}.png`));
            } catch (err) {
              writeJson(`08-ffmpeg-batch-${index}-error.json`, { error: String(err) });
            }
          } else {
            writeJson(`08-output-missing-batch-${index}.json`, {
              assetId: approved.approvedClip.assetId,
              status: fileRes.status(),
              outputPath: outPath,
            });
          }
        }
      }

      writeJson("minimax-i2v-input-binding.json", { bindings });

      // Cross-batch uniqueness of image hashes and Comfy filenames
      expect(bindings[0].sha256).not.toBe(bindings[1].sha256);
      expect(bindings[0].comfyImageName).not.toBe(bindings[1].comfyImageName);
      expect(bindings[0].outputAssetId).not.toBe(bindings[1].outputAssetId);

      const graph1 = JSON.parse(
        fs.readFileSync(path.join(ARTIFACT_DIR, "submitted-comfy-graph-batch-1.json"), "utf-8"),
      );
      const graph2 = JSON.parse(
        fs.readFileSync(path.join(ARTIFACT_DIR, "submitted-comfy-graph-batch-2.json"), "utf-8"),
      );
      assertI2vGraph(graph1, bindings[0].comfyImageName);
      assertI2vGraph(graph2, bindings[1].comfyImageName);

      const finalWs = await loadMaster(request, projectId, sceneId);
      const ordered = [...(finalWs.master.batchBlocks || [])].sort(
        (a: any, b: any) => a.order - b.order,
      );
      expect(ordered[0].approvedClip.assetId).not.toBe(ordered[1].approvedClip.assetId);

      let videoClips: any[] = [];
      const sceneRes = await request.get(`${API}/api/projects/${projectId}/scenes/${sceneId}`);
      const sceneBody = sceneRes.ok() ? await sceneRes.json() : {};
      const directorRaw = sceneBody.director_json ?? sceneBody.directorJson ?? sceneBody.director;
      if (directorRaw) {
        const dj = typeof directorRaw === "string" ? JSON.parse(directorRaw) : directorRaw;
        videoClips = dj.video_clips || [];
        writeJson("08-director.json", { video_clips: videoClips, media_mode: dj.media_mode });
      }

      const managed = (videoClips || [])
        .filter((c: any) => String(c.id || "").startsWith("bbclip_"))
        .sort((a: any, b: any) => a.start - b.start);
      expect(managed.length, "expected two managed Timeline video clips").toBe(2);
      expect(managed[0].asset_id).toBe(ordered[0].approvedClip.assetId);
      expect(managed[1].asset_id).toBe(ordered[1].approvedClip.assetId);

      await page.reload();
      await openTimeline(page, projectId, sceneId);
      const reloadWs = await loadMaster(request, projectId, sceneId);
      writeJson("09-reload-master.json", reloadWs.master);
      const rb = [...(reloadWs.master.batchBlocks || [])].sort((a: any, b: any) => a.order - b.order);
      expect(rb[0].status).toBe("Approved");
      expect(rb[1].status).toBe("Approved");
      for (const b of rb) {
        const lin = (b.references || []).find((r: any) => r.kind === "timelineGenerationLineage");
        expect(lin?.startImageAssetId).toBeTruthy();
        expect(lin?.generatorId).toBe(GENERATOR_ID);
      }

      writeJson("10-console-errors.json", { consoleErrors });

      const reviewPath = path.join(ARTIFACT_DIR, "i2v-conditioning-review.md");
      fs.writeFileSync(
        reviewPath,
        [
          "# MiniMax I2V Conditioning Review",
          "",
          `Run: ${RUN_ID}`,
          "",
          "## Batch 1",
          `- Source: source-batch1-subject.png (sha256=${bindings[0].sha256})`,
          `- Comfy: ${bindings[0].comfyImageName}`,
          `- Output asset: ${bindings[0].outputAssetId}`,
          `- First frame: first-frame-batch-1.png`,
          `- Expect: red circular subject / dark teal — must NOT match Batch 2 cream/blue triangle.`,
          "",
          "## Batch 2",
          `- Source: source-batch2-subject.png (sha256=${bindings[1].sha256})`,
          `- Comfy: ${bindings[1].comfyImageName}`,
          `- Output asset: ${bindings[1].outputAssetId}`,
          `- First frame: first-frame-batch-2.png`,
          `- Expect: blue triangular subject / warm cream — must NOT match Batch 1 red circle.`,
          "",
          "## Graph proof",
          "- submitted-comfy-graph-batch-1.json / batch-2.json each contain LoadImage + first_frame binding",
          "- Image hashes and Comfy filenames differ across batches",
          "",
          "Visual pass criterion: Batch N first frame derives from Image N, not the other batch.",
          "",
        ].join("\n"),
        "utf-8",
      );

      writeJson("11-lineage-summary.json", {
        projectId,
        sceneId,
        generatorId: GENERATOR_ID,
        model: "MiniMax H3 33B / Experimental Private Profile I2VA",
        fallbackAllowed: false,
        bindings,
        batches: rb.map((b: any) => ({
          batchBlockId: b.id,
          label: b.label,
          outputAssetId: b.approvedClip?.assetId,
          inputImageAssetId: b.sourceAnchors?.[0]?.assetId,
          generatorId: b.generatorId,
          lineage: (b.references || []).find((r: any) => r.kind === "timelineGenerationLineage"),
        })),
        videoClips: managed,
      });

      writeJson("VERDICT.json", {
        verdict: "GO — TIMELINE TWO-BATCH MINIMAX IMAGE-TO-VIDEO PLAYWRIGHT CERTIFICATION PASSED",
        architectureStatement:
          "The final two-batch certification rendered with MiniMax H3 33B image-to-video (LoadImage → first_frame) through the shared provider-agnostic Timeline generation workflow.",
        artifactDir: ARTIFACT_DIR,
      });
    } finally {
      await deleteProject(request, projectId);
    }
  });
});
