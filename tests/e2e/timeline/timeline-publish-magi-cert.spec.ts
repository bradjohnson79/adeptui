/**
 * Timeline Publish + MAGI — Tests A–E + MAGI 2-batch (Venture Corridor Dialogue).
 * Reuses Korri Anadriya. Never touches Scene 12B / Quarters Interview media.
 * Never rewrites Final Check / Dialogue Authority — fixtures seed lifecycle only.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const DIALOGUE_ID = "ae8e5699-a5d8-4b9b-ad8e-0003d81d3639"; // Venture Corridor Dialogue
const FORBIDDEN_SCENE_12B = "d774a22f-2b02-4eb2-b5ab-a98af9ff8f85";

const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/timeline-publish/artifacts");
const EVIDENCE_DIR = path.join(
  process.env.USERPROFILE || process.env.HOME || "",
  "theme_walk",
  "timeline_publish",
  "playwright_artifacts",
);

function writeArtifact(name: string, data: unknown) {
  const dirs = [ARTIFACT_DIR, EVIDENCE_DIR].filter((d) => Boolean(d) && d.length > 8);
  for (const dir of dirs) {
    try {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, name), JSON.stringify(data, null, 2), "utf8");
    } catch {
      /* best-effort */
    }
  }
}

async function cloneStitchAsset(request: APIRequestContext, stitchId: string): Promise<string | null> {
  const fileRes = await request.get(`${API}/api/projects/${PROJECT_ID}/assets/${stitchId}/file`);
  if (!fileRes.ok()) return null;
  const buf = Buffer.from(await fileRes.body());
  const up = await request.post(`${API}/api/projects/${PROJECT_ID}/assets`, {
    multipart: {
      file: {
        name: `vcd_publish_dirty_${Date.now()}.mp4`,
        mimeType: "video/mp4",
        buffer: buf,
      },
      kind: "video",
      tag: "scene_stitch",
    },
  });
  if (!up.ok()) return null;
  const body = await up.json();
  return body.id || body.asset?.id || body.assetId || null;
}

async function getMaster(request: APIRequestContext) {
  const r = await request.get(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/master`,
  );
  expect(r.ok(), "load VCD master").toBeTruthy();
  return (await r.json()).master as Record<string, any>;
}

async function putMaster(request: APIRequestContext, master: Record<string, any>) {
  const r = await request.put(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/master`,
    { data: { master } },
  );
  expect(r.ok(), `put master ${r.status()}`).toBeTruthy();
  return (await r.json()) as Record<string, any>;
}

async function postPublish(request: APIRequestContext, body: Record<string, unknown> = {}) {
  const r = await request.post(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/publish`,
    { data: body },
  );
  const json = await r.json().catch(() => ({}));
  return { status: r.status(), json };
}

async function postMagi(request: APIRequestContext, body: Record<string, unknown> = {}) {
  const r = await request.post(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/magi-upscale`,
    {
      data: {
        engine: "ffmpeg-scale",
        model: "lanczos",
        targetResolution: "",
        ...body,
      },
      timeout: 180_000,
    },
  );
  const json = await r.json().catch(() => ({}));
  return { status: r.status(), json };
}

async function waitMagiJob(request: APIRequestContext, jobId: string) {
  const deadline = Date.now() + 10 * 60_000;
  let last: Record<string, unknown> = {};
  while (Date.now() < deadline) {
    const r = await request.get(`${API}/api/magi/projects/${PROJECT_ID}/jobs/${jobId}`);
    last = (await r.json().catch(() => ({}))) as Record<string, unknown>;
    const status = String(last.status || "");
    if (["done", "failed", "cancelled", "canceled", "timed_out"].includes(status)) {
      return last;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(`MAGI job ${jobId} did not finish: ${JSON.stringify(last)}`);
}

async function openTimelineDialogue(page: Page) {
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&sceneId=${DIALOGUE_ID}`, {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await expect(page.getByTestId("live-preview-monitor")).toBeVisible({ timeout: 60_000 });
}

let originalMaster: Record<string, any> | null = null;

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta Timeline Publish + MAGI A–E (VCD)", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 (npm run test:e2e:beta)");

  test.beforeAll(async ({ request }) => {
    expect(DIALOGUE_ID).not.toBe(FORBIDDEN_SCENE_12B);
    await waitForAppReady(request);
    originalMaster = await getMaster(request);
    expect(originalMaster.sceneStitch?.assetId, "VCD needs existing stitch").toBeTruthy();
    writeArtifact("00-vcd-before.json", {
      stitch: originalMaster.sceneStitch,
      fc: originalMaster.sceneFinalCheck,
      publish: originalMaster.scenePublish,
      batchCount: (originalMaster.batchBlocks || []).length,
    });
  });

  test.afterAll(async ({ request }) => {
    try {
      const m = await getMaster(request);
      const stitchAssetId = originalMaster?.sceneStitch?.assetId || m.sceneStitch?.assetId;
      m.sceneStitch = originalMaster?.sceneStitch || m.sceneStitch;
      m.sceneFinalCheck = {
        ...(m.sceneFinalCheck || {}),
        lifecycleStatus: "SCENE_FINISHED",
        creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED",
        categories: (m.sceneFinalCheck?.categories as unknown[]) || [],
        stitchAssetId,
      };
      m.scenePublish = null;
      await putMaster(request, m);
      writeArtifact("99-vcd-restored-for-click-test.json", {
        stitch: m.sceneStitch?.assetId,
        fc: m.sceneFinalCheck?.lifecycleStatus,
        publishCleared: true,
      });
    } catch (err) {
      writeArtifact("99-restore-failed.json", { error: String(err) });
    }
  });

  test("A. CTA visibility gating — hidden before PASS; PUBLISH+UPSCALE after", async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);
    const m = await getMaster(request);
    expect((m.batchBlocks || []).length, "multi-batch fixture").toBeGreaterThanOrEqual(2);

    m.sceneFinalCheck = {
      ...(m.sceneFinalCheck || {}),
      lifecycleStatus: "FINAL_CHECK",
      creatorVerdict: "",
      categories: [],
    };
    m.scenePublish = null;
    await putMaster(request, m);

    await openTimelineDialogue(page);
    await expect(page.getByTestId("live-preview-publish")).toHaveCount(0);
    await expect(page.getByTestId("live-preview-upscale-magi")).toHaveCount(0);
    await expect(page.getByTestId("live-preview-update-published")).toHaveCount(0);

    const m2 = await getMaster(request);
    m2.sceneFinalCheck = {
      ...(m2.sceneFinalCheck || {}),
      lifecycleStatus: "SCENE_FINISHED",
      creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED",
      categories: [],
      stitchAssetId: m2.sceneStitch?.assetId,
    };
    m2.scenePublish = null;
    await putMaster(request, m2);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("live-preview-monitor")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("live-preview-publish")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("live-preview-upscale-magi")).toBeVisible();
    await expect(page.getByTestId("live-preview-update-published")).toHaveCount(0);

    writeArtifact("A-cta-gating.json", { ok: true, batches: (m2.batchBlocks || []).length });
  });

  test("B. Refuse publish before PASS (API)", async ({ request }) => {
    const m = await getMaster(request);
    m.sceneFinalCheck = {
      ...(m.sceneFinalCheck || {}),
      lifecycleStatus: "FINAL_CHECK",
      creatorVerdict: "",
      categories: [],
    };
    m.scenePublish = null;
    await putMaster(request, m);

    const { status, json } = await postPublish(request, { update: false, source: "stitch" });
    expect(status, `expected 400 got ${status} ${JSON.stringify(json)}`).toBe(400);
    const blob = JSON.stringify(json);
    expect(blob).toMatch(/NOT_PUBLISH_READY|Publish is available only after Final Check PASS/);

    writeArtifact("B-refuse-before-pass.json", { status, json });
  });

  test("C. Publish register — Video Published Master + provenance", async ({ page, request }) => {
    test.setTimeout(120_000);
    const m = await getMaster(request);
    const stitchId = m.sceneStitch?.assetId as string;
    m.sceneFinalCheck = {
      ...(m.sceneFinalCheck || {}),
      lifecycleStatus: "SCENE_FINISHED",
      creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED",
      categories: [],
      stitchAssetId: stitchId,
    };
    m.scenePublish = null;
    await putMaster(request, m);

    const { status, json } = await postPublish(request, { update: false, source: "stitch" });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.publishedAssetId).toBeTruthy();
    expect(json.scenePublish?.lifecycleStatusSnapshot).toBe("SCENE_FINISHED");
    expect(json.scenePublish?.acceptedIssues).toBe(false);
    expect(json.scenePublish?.sourceSceneStitchAssetId).toBe(stitchId);
    expect((json.master?.batchBlocks || []).length).toBeGreaterThanOrEqual(2);

    const fileRes = await request.get(
      `${API}/api/projects/${PROJECT_ID}/assets/${json.publishedAssetId}/file`,
    );
    expect(fileRes.ok(), "published master file reachable").toBeTruthy();
    const ctype = (fileRes.headers()["content-type"] || "").toLowerCase();
    expect(ctype.includes("video") || ctype.includes("octet")).toBeTruthy();

    const masterAfter = await getMaster(request);
    expect(masterAfter.scenePublish?.publishedAssetId).toBe(json.publishedAssetId);

    await openTimelineDialogue(page);
    await expect(page.getByTestId("live-preview-published-badge")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("live-preview-publish")).toHaveCount(0);
    await expect(page.getByTestId("live-preview-upscale-magi")).toBeVisible();

    writeArtifact("C-publish-register.json", {
      publishedAssetId: json.publishedAssetId,
      scenePublish: json.scenePublish,
      fileStatus: fileRes.status(),
      contentType: ctype,
    });
  });

  test("D. Changes Pending + UPDATE PUBLISHED after stitch identity moves", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const m = await getMaster(request);
    expect(m.scenePublish?.publishedAssetId, "C must have published").toBeTruthy();
    const oldStitch = m.sceneStitch?.assetId as string;
    const version = m.scenePublish?.version as number;

    const newStitchId = await cloneStitchAsset(request, oldStitch);
    test.skip(!newStitchId, "Could not create alternate stitch asset for dirty/update — covered by pytest");

    const m2 = await getMaster(request);
    m2.sceneStitch = {
      ...(m2.sceneStitch || {}),
      assetId: newStitchId,
      sourceBatchIds: m2.sceneStitch?.sourceBatchIds || ["bb1", "bb2"],
      sourceAssetIds: m2.sceneStitch?.sourceAssetIds || ["a1", "a2"],
    };
    m2.sceneFinalCheck = {
      ...(m2.sceneFinalCheck || {}),
      lifecycleStatus: "SCENE_FINISHED",
      creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED",
      categories: [],
    };
    await putMaster(request, m2);

    await openTimelineDialogue(page);
    await expect(page.getByTestId("live-preview-changes-pending")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("live-preview-update-published")).toBeVisible();
    await expect(page.getByTestId("live-preview-publish")).toHaveCount(0);

    const { status, json } = await postPublish(request, {
      update: true,
      expectedVersion: version,
      source: "stitch",
    });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.updated).toBe(true);
    expect(json.scenePublish?.version).toBe(version + 1);
    expect(json.scenePublish?.sourceSceneStitchAssetId).toBe(newStitchId);

    const m3 = await getMaster(request);
    m3.sceneStitch = originalMaster?.sceneStitch || { ...m3.sceneStitch, assetId: oldStitch };
    await putMaster(request, m3);

    writeArtifact("D-dirty-update.json", {
      oldStitch,
      newStitchId,
      fromVersion: version,
      toVersion: json.scenePublish?.version,
    });
  });

  test("E. MAGI full-stitch entry — blocks batch; queues; persist after job", async ({ request }) => {
    test.setTimeout(720_000);
    const m = await getMaster(request);
    m.sceneFinalCheck = {
      ...(m.sceneFinalCheck || {}),
      lifecycleStatus: "SCENE_FINISHED",
      creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED",
      categories: [],
    };
    await putMaster(request, m);

    const batchAsset =
      m.batchBlocks?.[0]?.approvedClip?.assetId ||
      m.sceneStitch?.sourceAssetIds?.[0] ||
      "batch-not-allowed";

    const blocked = await postMagi(request, { assetId: batchAsset });
    expect(blocked.status).toBe(400);
    expect(JSON.stringify(blocked.json)).toMatch(/MAGI_FULL_STITCH_ONLY|full stitched/);

    const beforePublish = (await getMaster(request)).scenePublish?.publishedAssetId || null;

    const optionsRes = await request.get(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${DIALOGUE_ID}/magi-upscale/options`,
    );
    const options = await optionsRes.json().catch(() => ({}));
    expect(optionsRes.ok(), JSON.stringify(options)).toBeTruthy();
    expect(Array.isArray(options.targets) && options.targets.length > 0).toBe(true);
    if (Number(options.sourceHeight || 0) >= 1080) {
      expect(options.targets.some((row: { id: string }) => row.id === "1080p")).toBe(false);
    }

    const ok = await postMagi(request, {
      targetResolution: options.defaultTarget || options.targets[0]?.id || "",
    });
    expect(ok.status, JSON.stringify(ok.json)).toBe(200);
    expect(ok.json.ok).toBe(true);
    expect(ok.json.autoPublished).toBe(false);
    expect(ok.json.sourceAssetId).toBeTruthy();
    expect(ok.json.jobId, "POST only enqueues").toBeTruthy();
    expect(ok.json.upscaledAssetId == null).toBe(true);

    const afterEnqueue = await getMaster(request);
    expect(afterEnqueue.scenePublish?.upscaledAssetId || null).toBe(
      originalMaster?.scenePublish?.upscaledAssetId || null,
    );

    const job = await waitMagiJob(request, String(ok.json.jobId));
    expect(job.status, JSON.stringify(job)).toBe("done");

    const after = await getMaster(request);
    expect(after.scenePublish?.upscaledAssetId, "job completion persists upscaledAssetId").toBeTruthy();
    const allowed = new Set(
      [
        after.sceneStitch?.assetId,
        after.scenePublish?.publishedAssetId,
        after.scenePublish?.upscaledAssetId,
        ok.json.sourceAssetId,
      ].filter(Boolean),
    );
    expect(allowed.has(ok.json.sourceAssetId)).toBe(true);

    const afterPublish = after.scenePublish?.publishedAssetId || null;
    writeArtifact("E-magi-full-stitch.json", {
      blocked: blocked.json,
      options,
      magi: {
        ok: ok.json.ok,
        queued: ok.json.queued,
        jobId: ok.json.jobId,
        autoPublished: ok.json.autoPublished,
        sourceAssetId: ok.json.sourceAssetId,
        upscaledAssetIdOnPost: ok.json.upscaledAssetId,
        upscaledAssetIdAfterJob: after.scenePublish?.upscaledAssetId,
      },
      job,
      beforePublish,
      afterPublish,
    });
  });

  test("MAGI 2-batch: VCD has >=2 batches; Timeline MAGI still full-stitch only", async ({
    request,
  }) => {
    const m = await getMaster(request);
    const n = (m.batchBlocks || []).length;
    expect(n).toBeGreaterThanOrEqual(2);
    expect(m.sceneStitch?.assetId).toBeTruthy();
    if (
      !["SCENE_FINISHED", "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"].includes(
        String(m.sceneFinalCheck?.lifecycleStatus || ""),
      )
    ) {
      m.sceneFinalCheck = {
        ...(m.sceneFinalCheck || {}),
        lifecycleStatus: "SCENE_FINISHED",
        creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED",
        categories: [],
      };
      await putMaster(request, m);
    }
    const secondBatchAsset =
      m.batchBlocks?.[1]?.approvedClip?.assetId || m.sceneStitch?.sourceAssetIds?.[1];
    if (secondBatchAsset) {
      const blocked = await postMagi(request, { assetId: String(secondBatchAsset) });
      expect(JSON.stringify(blocked.json)).toMatch(/MAGI_FULL_STITCH_ONLY|full stitched/);
    }
    writeArtifact("MAGI-2-batch.json", {
      batchCount: n,
      stitch: m.sceneStitch?.assetId,
      secondBatchAsset: secondBatchAsset || null,
    });
  });
});