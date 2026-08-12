/**
 * Timeline Multi-Batch — End-to-End Wiring Certification
 * (NO AUTOMATED GPU GENERATION)
 *
 * Certifies the full pathway UP TO the provider execution boundary:
 * multi-batch authoring, timeline-driven Preview Monitor, Generate Current /
 * Generate Scene wiring, sequential queue contract (request snapshot created
 * vs provider job submitted), completion binding by immutable batch lineage,
 * re-take, stop/resume safety, and scale. Real GPU generation remains the
 * manual creator gate.
 *
 * Requires Beta API started with ADEPT_TIMELINE_CERT_STUB=1 (env-gated
 * StubCertAdapter replaces the provider execution boundary) and
 * ADEPT_BETA_TARGET=1. Serial, workers=1, retries=0.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/timeline-multi-batch/artifacts");
const CERT = `${API}/api/director-timeline/cert`;
const TL = `${API}/api/director-timeline`;
const STUB_GENERATOR = "cert-stub-local";

// 8x8 solid PNGs — visually and semantically distinguishable cert inputs.
const PNG_RED = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEklEQVR4nGP4z8CAFWEXHbQSACj/P8Fu7N9hAAAAAElFTkSuQmCC",
  "base64",
);
const PNG_BLUE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEElEQVR4nGNgYPiPAw0pCQCpcD/BFMrqcwAAAABJRU5ErkJggg==",
  "base64",
);

let STUB_ON = false;

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resetCert(request: APIRequestContext) {
  const r = await request.post(`${CERT}/reset`);
  expect(r.ok(), "cert reset requires ADEPT_TIMELINE_CERT_STUB=1").toBeTruthy();
}

async function readSink(request: APIRequestContext): Promise<Array<Record<string, any>>> {
  const r = await request.get(`${CERT}/requests`);
  expect(r.ok()).toBeTruthy();
  return (await r.json()).requests || [];
}

async function setStubState(
  request: APIRequestContext,
  jobId: string,
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled",
  outputAssetIds?: string[],
  errorMessage?: string,
) {
  const r = await request.post(`${CERT}/stub-jobs/${jobId}/state`, {
    data: { state, outputAssetIds: outputAssetIds ?? null, errorMessage: errorMessage ?? null },
  });
  expect(r.ok(), `set stub job ${jobId} → ${state}`).toBeTruthy();
}

async function getMaster(request: APIRequestContext, pid: string, sid: string) {
  const r = await request.get(`${TL}/projects/${pid}/scenes/${sid}/master`);
  expect(r.ok(), "master GET").toBeTruthy();
  return (await r.json()).master;
}

async function newScene(request: APIRequestContext, name: string) {
  const project = await createTempProject(request, name);
  const sres = await request.get(`${API}/api/projects/${project.id}/scenes`);
  expect(sres.ok()).toBeTruthy();
  const scenes = await sres.json();
  const slist = Array.isArray(scenes) ? scenes : scenes.scenes || [];
  expect(slist.length).toBeGreaterThan(0);
  return { pid: project.id as string, sid: slist[0].id as string };
}

async function addBatch(request: APIRequestContext, pid: string, sid: string, plannedDuration = 5, atOrder?: number) {
  const r = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches`, {
    data: { plannedDuration, ...(atOrder !== undefined ? { atOrder } : {}) },
  });
  expect(r.ok(), "add batch").toBeTruthy();
  return (await r.json()).batch;
}

async function configBatch(
  request: APIRequestContext,
  pid: string,
  sid: string,
  batchId: string,
  cfg: { prompt: string; plannedDuration?: number; startImageAssetId?: string; generatorId?: string },
) {
  const r = await request.patch(`${TL}/projects/${pid}/scenes/${sid}/batches/${batchId}`, {
    data: {
      generatorId: cfg.generatorId ?? STUB_GENERATOR,
      ...(cfg.plannedDuration !== undefined ? { plannedDuration: cfg.plannedDuration } : {}),
      promptSegments: [
        {
          id: `ps-${batchId.slice(-6)}`,
          start: 0,
          length: cfg.plannedDuration ?? 5,
          text: cfg.prompt,
          role: "primary",
          strength: 1,
          anchorIds: [],
          executionStrategy: "compiled",
          versionId: `psv-${batchId.slice(-6)}`,
        },
      ],
      ...(cfg.startImageAssetId
        ? { sourceAnchors: [{ kind: "image", assetId: cfg.startImageAssetId, label: "start", atTime: 0, strength: 1 }] }
        : {}),
    },
  });
  expect(r.ok(), "config batch").toBeTruthy();
}

async function uploadImage(request: APIRequestContext, pid: string, tag: string, png: Buffer): Promise<string> {
  const r = await request.post(`${API}/api/projects/${pid}/assets`, {
    multipart: { file: { name: `${tag}.png`, mimeType: "image/png", buffer: png }, tag, kind: "image" },
  });
  expect(r.ok(), `upload ${tag}`).toBeTruthy();
  return (await r.json()).id as string;
}

async function generateBatch(request: APIRequestContext, pid: string, sid: string, batchId: string) {
  const r = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${batchId}/generate`);
  expect(r.ok(), `generate batch ${batchId}`).toBeTruthy();
  const body = await r.json();
  expect(body.ok, `generate batch ${batchId} ok`).toBeTruthy();
  return body;
}

async function completeAndApprove(
  request: APIRequestContext,
  pid: string,
  sid: string,
  batchId: string,
  snapshotId: string,
  assetId: string,
  duration = 5,
) {
  const c = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${batchId}/complete`, {
    data: { assetId, generatedDuration: duration, executionSnapshotId: snapshotId },
  });
  expect(c.ok(), "complete batch").toBeTruthy();
  const cbody = await c.json();
  expect(cbody.ok).toBeTruthy();
  const candId = cbody.candidate.id as string;
  const a = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${batchId}/approve`, {
    data: { candidateId: candId },
  });
  expect(a.ok(), "approve batch").toBeTruthy();
  return (await a.json()) as Record<string, any>;
}

async function gotoTimeline(page: Page, pid: string) {
  await page.goto(`/project/${pid}?workspace=timeline`);
  await page.waitForLoadState("domcontentloaded");
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 30_000 });
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta timeline multi-batch wiring cert (no GPU)", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test.beforeAll(async ({ request }) => {
    const r = await request.get(`${CERT}/requests`);
    STUB_ON = r.ok();
  });

  test("0. app ready + cert stub enabled", async ({ request }) => {
    await waitForAppReady(request);
    expect(STUB_ON, "Beta API must run with ADEPT_TIMELINE_CERT_STUB=1 (restart Beta with the env var)").toBeTruthy();
    const gens = await (await request.get(`${TL}/generators`)).json();
    const ids = (gens.generators || []).map((g: { id: string }) => g.id);
    expect(ids, "cert stub generator registered").toContain(STUB_GENERATOR);
  });

  test("A. multi-batch authoring: identity, order independence, isolation, reload, undo/redo", async ({ page, request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert A");
    try {
      const m0 = await getMaster(request, pid, sid);
      const b1 = m0.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 5);
      const b3 = await addBatch(request, pid, sid, 5);
      const ids = [b1.id, b2.id, b3.id];

      // Stable IDs across reload
      const m1 = await getMaster(request, pid, sid);
      expect(m1.batchBlocks.map((b: { id: string }) => b.id)).toEqual(ids);

      // Order independent of identity: insert at order 0 — IDs never rewritten.
      const b0 = await addBatch(request, pid, sid, 5, 0);
      const m2 = await getMaster(request, pid, sid);
      const sorted = m2.batchBlocks.slice().sort((a: any, b: any) => a.order - b.order);
      expect(sorted[0].id).toBe(b0.id);
      expect(new Set(m2.batchBlocks.map((b: any) => b.id)).size).toBe(4);
      for (const id of ids) {
        expect(m2.batchBlocks.some((b: any) => b.id === id), `batch ${id} survives reorder`).toBeTruthy();
      }

      // Add media to Batch b2 → other batches untouched
      const assetX = await uploadImage(request, pid, "cert-a-x", PNG_RED);
      const clip = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${b2.id}/clips`, {
        data: { kind: "image", assetId: assetX, start: 0, length: 2, label: "B2 image" },
      });
      expect(clip.ok()).toBeTruthy();
      const m3 = await getMaster(request, pid, sid);
      for (const b of m3.batchBlocks) {
        if (b.id === b2.id) expect(b.visualClips.length, "b2 grew").toBe(1);
        else expect((b.visualClips || []).length, `batch ${b.id} untouched`).toBe(0);
      }

      // UI: batch lane renders all batches; selection works; reload preserves.
      await gotoTimeline(page, pid);
      for (const id of [b0.id, b1.id, b2.id, b3.id]) {
        await expect(page.getByTestId(`timeline-batch-${id}`), `lane shows ${id}`).toBeVisible({ timeout: 20_000 });
      }
      await page.getByTestId(`timeline-batch-${b2.id}`).click();
      await expect(page.getByTestId(`timeline-batch-${b2.id}`)).toHaveClass(/active/);

      // Undo/redo isolated: track-level edits never touch batch state.
      const before = await getMaster(request, pid, sid);
      await page.getByTestId("timeline-toolbar-prompt-add").click();
      const undoBtn = page.getByRole("button", { name: "Undo the last Timeline edit" });
      await expect(undoBtn).toBeEnabled({ timeout: 15_000 });
      await undoBtn.click();
      const redoBtn = page.getByRole("button", { name: "Redo the last undone Timeline edit" });
      await expect(redoBtn).toBeEnabled({ timeout: 15_000 });
      await redoBtn.click();
      const after = await getMaster(request, pid, sid);
      expect(after.batchBlocks.map((b: any) => b.id).sort()).toEqual(before.batchBlocks.map((b: any) => b.id).sort());
      const b2after = after.batchBlocks.find((b: any) => b.id === b2.id);
      expect(b2after.visualClips.length, "undo/redo never touched batch clips").toBe(1);

      // Reload persistence
      await page.reload();
      await page.waitForLoadState("domcontentloaded");
      for (const id of [b0.id, b1.id, b2.id, b3.id]) {
        await expect(page.getByTestId(`timeline-batch-${id}`), `reload keeps ${id}`).toBeVisible({ timeout: 20_000 });
      }
      writeArtifact("A-multi-batch-authoring.json", { ids: [b0.id, ...ids], orderIndependent: true, undoRedoIsolated: true });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("B. preview monitor is timeline-driven (image + prompt lower-third, cross-batch)", async ({ page, request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert B");
    try {
      const assetA = await uploadImage(request, pid, "cert-red", PNG_RED);
      const assetB = await uploadImage(request, pid, "cert-blue", PNG_BLUE);
      let m = await getMaster(request, pid, sid);
      const bA = m.batchBlocks[0];
      const bB = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, bA.id, { prompt: "PROMPT ALPHA — red dawn over the valley", plannedDuration: 5 });
      await configBatch(request, pid, sid, bB.id, { prompt: "PROMPT BRAVO — blue midnight in the city", plannedDuration: 5 });
      for (const [bid, asset] of [
        [bA.id, assetA],
        [bB.id, assetB],
      ] as const) {
        const r = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${bid}/clips`, {
          data: { kind: "image", assetId: asset, start: 0, length: 5, label: "hero" },
        });
        expect(r.ok()).toBeTruthy();
      }

      await gotoTimeline(page, pid);
      const lane = page.locator(".track-ruler__lane");
      await expect(lane).toBeVisible({ timeout: 20_000 });
      const box = await lane.boundingBox();
      expect(box).toBeTruthy();

      // Playhead over Batch A (25% of 10s board = 2.5s)
      await lane.click({ position: { x: box!.width * 0.25, y: Math.max(2, box!.height / 2) } });
      const img = page.getByTestId("live-preview-image");
      await expect(img, "preview shows Batch A image, never Idle").toBeVisible({ timeout: 20_000 });
      await expect(img).toHaveAttribute("src", new RegExp(assetA), { timeout: 20_000 });
      const lower = page.getByTestId("timeline-prompt-lower-third");
      await expect(lower, "lower-third shows Prompt A").toBeVisible({ timeout: 20_000 });
      await expect(lower).toContainText("PROMPT ALPHA");

      // Cross-batch transition: playhead into Batch B (75% = 7.5s)
      await lane.click({ position: { x: box!.width * 0.75, y: Math.max(2, box!.height / 2) } });
      await expect(img, "preview transitions to Batch B image").toHaveAttribute("src", new RegExp(assetB), { timeout: 20_000 });
      await expect(lower).toContainText("PROMPT BRAVO", { timeout: 20_000 });

      await page.screenshot({ path: path.join(ARTIFACT_DIR, "B-preview-timeline-driven.png") });
      writeArtifact("B-preview-timeline-driven.json", { assetA, assetB, crossBatchTransition: true });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("C. Generate Current targets the selected batch only (UI)", async ({ page, request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert C");
    try {
      const assetA = await uploadImage(request, pid, "cert-c-a", PNG_RED);
      const assetB = await uploadImage(request, pid, "cert-c-b", PNG_BLUE);
      const m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, b1.id, { prompt: "BATCH ONE prompt", plannedDuration: 5, startImageAssetId: assetA });
      await configBatch(request, pid, sid, b2.id, { prompt: "BATCH TWO prompt", plannedDuration: 8, startImageAssetId: assetB });

      await gotoTimeline(page, pid);
      await page.getByTestId(`timeline-batch-${b2.id}`).click();
      await expect(page.getByTestId(`timeline-batch-${b2.id}`)).toHaveClass(/active/);
      await page.getByTestId("timeline-gen-batch").click();

      await expect
        .poll(async () => (await readSink(request)).length, { timeout: 20_000 })
        .toBe(1);
      const sink = await readSink(request);
      const req = sink[0].request;
      expect(req.batchBlockId, "request targets Batch 2").toBe(b2.id);
      expect(req.prompt, "Batch 2 prompt").toContain("BATCH TWO");
      expect(req.prompt).not.toContain("BATCH ONE");
      expect(req.duration, "Batch 2 duration").toBe(8);
      expect(req.startImageAssetId, "Batch 2 start image").toBe(assetB);
      expect(req.generatorId).toBe(STUB_GENERATOR);
      writeArtifact("C-generate-current-selected-batch.json", { batchBlockId: req.batchBlockId, executionSnapshotId: req.executionSnapshotId });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("D. Generate Scene (parallel): one independent immutable request per batch", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert D");
    try {
      const assetA = await uploadImage(request, pid, "cert-d-a", PNG_RED);
      const assetB = await uploadImage(request, pid, "cert-d-b", PNG_BLUE);
      let m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 5);
      const b3 = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, b1.id, { prompt: "D-ONE", plannedDuration: 5, startImageAssetId: assetA });
      await configBatch(request, pid, sid, b2.id, { prompt: "D-TWO", plannedDuration: 8, startImageAssetId: assetB });
      await configBatch(request, pid, sid, b3.id, { prompt: "D-THREE", plannedDuration: 2 });

      // Parallel orchestration: all eligible batches submit immediately.
      m = await getMaster(request, pid, sid);
      m.orchestratorMode = "parallel";
      const put = await request.put(`${TL}/projects/${pid}/scenes/${sid}/master`, { data: { master: m } });
      expect(put.ok(), "set parallel mode").toBeTruthy();

      const gen = await request.post(`${TL}/projects/${pid}/scenes/${sid}/generate`, { data: { scope: "full" } });
      expect(gen.ok()).toBeTruthy();
      const body = await gen.json();
      expect(body.ok, JSON.stringify(body.errors)).toBeTruthy();
      expect(body.orchestratorMode).toBe("parallel");

      const sink = await readSink(request);
      expect(sink.length, "one provider submission per batch").toBe(3);
      const byBatch = new Map(sink.map((r: any) => [r.request.batchBlockId, r.request]));
      expect(byBatch.size).toBe(3);
      const snapIds = new Set(sink.map((r: any) => r.request.executionSnapshotId));
      expect(snapIds.size, "distinct immutable snapshots").toBe(3);

      const r1 = byBatch.get(b1.id)!;
      expect(r1.prompt).toContain("D-ONE");
      expect(r1.duration).toBe(5);
      expect(r1.startImageAssetId).toBe(assetA);
      const r2 = byBatch.get(b2.id)!;
      expect(r2.prompt).toContain("D-TWO");
      expect(r2.duration).toBe(8);
      expect(r2.startImageAssetId).toBe(assetB);
      const r3 = byBatch.get(b3.id)!;
      expect(r3.prompt).toContain("D-THREE");
      expect(r3.duration).toBe(2);
      // No shared mutable payload: each request carries only its own batch data.
      expect(r2.prompt).not.toContain("D-ONE");
      expect(r3.prompt).not.toContain("D-TWO");

      const after = await getMaster(request, pid, sid);
      for (const b of after.batchBlocks) {
        expect(b.status, `batch ${b.id} Generating`).toBe("Generating");
      }
      writeArtifact("D-generate-scene-isolation.json", { requests: sink.length, snapshots: snapIds.size });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("E. sequential queue contract: snapshot created != provider submitted; concurrency = 1", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert E");
    try {
      let m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 5);
      const b3 = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, b1.id, { prompt: "E-ONE", plannedDuration: 5 });
      await configBatch(request, pid, sid, b2.id, { prompt: "E-TWO", plannedDuration: 5 });
      await configBatch(request, pid, sid, b3.id, { prompt: "E-THREE", plannedDuration: 5 });

      const gen = await request.post(`${TL}/projects/${pid}/scenes/${sid}/generate`, { data: { scope: "full" } });
      expect(gen.ok()).toBeTruthy();
      expect((await gen.json()).orchestratorMode).toBe("sequential_continuity");

      // REQUEST SNAPSHOT CREATED for all three; PROVIDER JOB SUBMITTED for B1 only.
      let sink = await readSink(request);
      expect(sink.length, "submission concurrency = 1").toBe(1);
      expect(sink[0].request.batchBlockId).toBe(b1.id);
      m = await getMaster(request, pid, sid);
      const byId = Object.fromEntries(m.batchBlocks.map((b: any) => [b.id, b]));
      expect(byId[b1.id].status).toBe("Generating");
      expect(byId[b2.id].status, "B2 snapshot READY, waiting").toBe("Queued");
      expect(byId[b3.id].status, "B3 snapshot READY, waiting").toBe("Queued");
      const stagedSnap2 = byId[b2.id].pendingSnapshotId;
      const stagedSnap3 = byId[b3.id].pendingSnapshotId;
      expect(stagedSnap2).toBeTruthy();
      expect(stagedSnap3).toBeTruthy();
      expect(m.executionSnapshots[stagedSnap2].immutable, "staged snapshot immutable").toBeTruthy();
      expect(m.executionSnapshots[stagedSnap3].immutable).toBeTruthy();

      // Synchronous chain: B1 terminal (complete+approve) → B2 submitted with its STAGED snapshot.
      const snap1 = byId[b1.id].generationJobs[0].executionSnapshotId;
      const approved = await completeAndApprove(request, pid, sid, b1.id, snap1, "cert-asset-out-1");
      expect(approved.sequentialChain?.submitted, "chain submits B2").toBeTruthy();
      expect(approved.sequentialChain?.batchBlockId).toBe(b2.id);
      sink = await readSink(request);
      expect(sink.length).toBe(2);
      expect(sink[1].request.batchBlockId).toBe(b2.id);
      expect(sink[1].request.executionSnapshotId, "B2 reuses staged snapshot").toBe(stagedSnap2);
      m = await getMaster(request, pid, sid);
      const byId2 = Object.fromEntries(m.batchBlocks.map((b: any) => [b.id, b]));
      expect(byId2[b2.id].status).toBe("Generating");
      expect(byId2[b3.id].status, "B3 still waiting — concurrency stays 1").toBe("Queued");

      // Watcher-driven chain: advance B2's stub job deterministically → succeeded.
      const job2 = sink[1].jobId;
      await setStubState(request, job2, "succeeded", ["cert-asset-out-2"]);
      await expect
        .poll(
          async () => {
            const mm = await getMaster(request, pid, sid);
            const map = Object.fromEntries(mm.batchBlocks.map((b: any) => [b.id, b]));
            return `${map[b2.id].status}/${map[b3.id].status}`;
          },
          { timeout: 30_000, intervals: [1_000, 2_000, 3_000] },
        )
        .toBe("Approved/Generating");
      sink = await readSink(request);
      expect(sink.length, "B3 submitted only after B2 terminal").toBe(3);
      expect(sink[2].request.batchBlockId).toBe(b3.id);
      expect(sink[2].request.executionSnapshotId).toBe(stagedSnap3);
      writeArtifact("E-sequential-queue-contract.json", {
        submissionsInOrder: sink.map((r: any) => r.request.batchBlockId),
        stagedSnapshotsReused: true,
      });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("F. completion binding: by immutable batch lineage — never selection, index, or scene.output_path", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert F");
    try {
      const assetA = await uploadImage(request, pid, "cert-f-a", PNG_RED);
      const assetB = await uploadImage(request, pid, "cert-f-b", PNG_BLUE);
      const outA = await uploadImage(request, pid, "cert-f-out-a", PNG_RED);
      const outB = await uploadImage(request, pid, "cert-f-out-b", PNG_BLUE);
      const m = await getMaster(request, pid, sid);
      const bA = m.batchBlocks[0];
      const bB = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, bA.id, { prompt: "F-ALPHA", plannedDuration: 5, startImageAssetId: assetA });
      await configBatch(request, pid, sid, bB.id, { prompt: "F-BRAVO", plannedDuration: 5, startImageAssetId: assetB });

      const sceneBefore = await (await request.get(`${API}/api/projects/${pid}/scenes/${sid}`)).json().catch(() => ({}));
      await generateBatch(request, pid, sid, bA.id);
      await generateBatch(request, pid, sid, bB.id);
      const m2 = await getMaster(request, pid, sid);
      const byId = Object.fromEntries(m2.batchBlocks.map((b: any) => [b.id, b]));
      const snapA = byId[bA.id].generationJobs[0].executionSnapshotId;
      const snapB = byId[bB.id].generationJobs[0].executionSnapshotId;

      // Complete OUT OF ORDER: B first, then A. Binding must follow lineage.
      await completeAndApprove(request, pid, sid, bB.id, snapB, outB);
      await completeAndApprove(request, pid, sid, bA.id, snapA, outA);

      const m3 = await getMaster(request, pid, sid);
      const byId3 = Object.fromEntries(m3.batchBlocks.map((b: any) => [b.id, b]));
      expect(byId3[bA.id].approvedClip?.assetId, "Output A binds only to Batch A").toBe(outA);
      expect(byId3[bA.id].approvedClip?.executionSnapshotId).toBe(snapA);
      expect(byId3[bB.id].approvedClip?.assetId, "Output B binds only to Batch B").toBe(outB);
      expect(byId3[bB.id].approvedClip?.executionSnapshotId).toBe(snapB);
      // batches[0] is Batch A — yet Batch B (completed first) did not steal Output A.

      // scene.output_path untouched by batch completion
      const sceneAfter = await (await request.get(`${API}/api/projects/${pid}/scenes/${sid}`)).json().catch(() => ({}));
      expect(
        (sceneAfter as any).output_path ?? (sceneAfter as any).outputPath ?? null,
        "scene.output_path unchanged",
      ).toBe((sceneBefore as any).output_path ?? (sceneBefore as any).outputPath ?? null);

      // Placement follows batch ORDER, not completion order.
      const director = await (await request.get(`${API}/api/projects/${pid}/scenes/${sid}/director`)).json();
      const managed = (director.video_clips || []).filter((c: any) => String(c.id).startsWith("bbclip_"));
      expect(managed.length).toBe(2);
      expect(managed[0].asset_id, "first placed clip is Batch A output").toBe(outA);
      expect(managed[1].asset_id).toBe(outB);
      expect(managed[0].start).toBeLessThan(managed[1].start);
      writeArtifact("F-completion-binding.json", { batchA: { id: bA.id, asset: outA, snap: snapA }, batchB: { id: bB.id, asset: outB, snap: snapB } });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("G. re-take wiring: new request targets Batch B with new snapshot; Batch A untouched", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert G");
    try {
      const m = await getMaster(request, pid, sid);
      const bA = m.batchBlocks[0];
      const bB = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, bA.id, { prompt: "G-ALPHA", plannedDuration: 5 });
      await configBatch(request, pid, sid, bB.id, { prompt: "G-BRAVO", plannedDuration: 5 });

      await generateBatch(request, pid, sid, bB.id);
      let sink = await readSink(request);
      expect(sink.length).toBe(1);
      const firstSnap = sink[0].request.executionSnapshotId;

      const rt = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${bB.id}/retake`, { data: { mode: "directed" } });
      expect(rt.ok()).toBeTruthy();
      const rtBody = await rt.json();
      expect(rtBody.ok).toBeTruthy();
      expect(rtBody.priorSnapshotsPreserved).toBeTruthy();

      sink = await readSink(request);
      expect(sink.length, "re-take adds exactly one new request").toBe(2);
      const retakeReq = sink[1].request;
      expect(retakeReq.batchBlockId, "re-take targets Batch B").toBe(bB.id);
      expect(retakeReq.executionSnapshotId, "lineage advances — new snapshot").not.toBe(firstSnap);
      expect(retakeReq.prompt).toContain("G-BRAVO");

      const m2 = await getMaster(request, pid, sid);
      const byId = Object.fromEntries(m2.batchBlocks.map((b: any) => [b.id, b]));
      expect(byId[bA.id].generationJobs.length, "Batch A untouched").toBe(0);
      expect(sink.every((r: any) => r.request.batchBlockId !== bA.id), "no request ever targets Batch A").toBeTruthy();
      // Prior snapshot preserved immutably
      expect(m2.executionSnapshots[firstSnap]).toBeTruthy();
      writeArtifact("G-retake-wiring.json", { batchBlockId: bB.id, firstSnap, retakeSnap: retakeReq.executionSnapshotId });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("H. cancel/stop wiring: execution stops; authoring state and completed outputs preserved", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert H");
    try {
      let m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 5);
      const b3 = await addBatch(request, pid, sid, 5);
      const b4 = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, b1.id, { prompt: "H-ONE", plannedDuration: 5 });
      await configBatch(request, pid, sid, b2.id, { prompt: "H-TWO", plannedDuration: 5 });
      await configBatch(request, pid, sid, b3.id, { prompt: "H-THREE", plannedDuration: 5 });
      await configBatch(request, pid, sid, b4.id, { prompt: "H-FOUR", plannedDuration: 5 });
      const clipAsset = await uploadImage(request, pid, "cert-h-clip", PNG_RED);
      await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${b2.id}/clips`, {
        data: { kind: "image", assetId: clipAsset, start: 0, length: 2, label: "B2 clip" },
      });

      // Complete b4 first so a completed output exists before the stop.
      await generateBatch(request, pid, sid, b4.id);
      m = await getMaster(request, pid, sid);
      const snap4 = m.batchBlocks.find((b: any) => b.id === b4.id).generationJobs[0].executionSnapshotId;
      await completeAndApprove(request, pid, sid, b4.id, snap4, "cert-h-out-4");
      await resetCert(request); // isolate sink for the scene-run portion

      const gen = await request.post(`${TL}/projects/${pid}/scenes/${sid}/generate`, { data: { scope: "full" } });
      expect(gen.ok()).toBeTruthy();
      const sinkBefore = await readSink(request);
      expect(sinkBefore.length, "only B1 submitted (sequential)").toBe(1);

      const cancel = await request.post(`${TL}/projects/${pid}/scenes/${sid}/cancel`, {
        data: { action: "stop_remaining_scene_jobs" },
      });
      expect(cancel.ok()).toBeTruthy();
      const cbody = await cancel.json();
      expect(cbody.ok).toBeTruthy();
      expect(cbody.preservedCompletedBatchIds, "completed batch preserved").toContain(b4.id);

      const after = await getMaster(request, pid, sid);
      const byId = Object.fromEntries(after.batchBlocks.map((b: any) => [b.id, b]));
      // STOP != DELETE: all authoring state intact.
      expect(after.batchBlocks.length, "no batch deleted").toBe(4);
      for (const id of [b1.id, b2.id, b3.id]) {
        expect(byId[id].status).toBe("Cancelled");
        expect(byId[id].promptSegments[0].text, `prompt preserved on ${id}`).toContain("H-");
        expect(byId[id].duration.plannedDuration, `timing preserved on ${id}`).toBe(5);
      }
      expect(byId[b2.id].visualClips.length, "clips preserved").toBe(1);
      expect(byId[b4.id].status).toBe("Approved");
      expect(byId[b4.id].approvedClip?.assetId, "completed output preserved").toBe("cert-h-out-4");
      const sinkAfter = await readSink(request);
      expect(sinkAfter.length, "stop never triggers new submissions").toBe(1);
      writeArtifact("H-cancel-stop-wiring.json", { preserved: cbody.preservedCompletedBatchIds, batches: after.batchBlocks.length });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("I. resume wiring: approved batch never resubmitted; interrupted + queued continue", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert I");
    try {
      let m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 5);
      const b3 = await addBatch(request, pid, sid, 5);
      await configBatch(request, pid, sid, b1.id, { prompt: "I-ONE", plannedDuration: 5 });
      await configBatch(request, pid, sid, b2.id, { prompt: "I-TWO", plannedDuration: 5 });
      await configBatch(request, pid, sid, b3.id, { prompt: "I-THREE", plannedDuration: 5 });

      await request.post(`${TL}/projects/${pid}/scenes/${sid}/generate`, { data: { scope: "full" } });
      // B1 complete; chain submits B2.
      m = await getMaster(request, pid, sid);
      const snap1 = m.batchBlocks.find((b: any) => b.id === b1.id).generationJobs[0].executionSnapshotId;
      await completeAndApprove(request, pid, sid, b1.id, snap1, "cert-i-out-1");

      // Interrupt B2 (cancel active local job) — B3 stays Queued.
      const cancel = await request.post(`${TL}/projects/${pid}/scenes/${sid}/cancel`, {
        data: { action: "cancel_active_local_job", batchBlockIds: [b2.id] },
      });
      expect(cancel.ok()).toBeTruthy();
      m = await getMaster(request, pid, sid);
      let byId = Object.fromEntries(m.batchBlocks.map((b: any) => [b.id, b]));
      expect(byId[b1.id].status).toBe("Approved");
      expect(byId[b2.id].status).toBe("Cancelled");
      expect(byId[b3.id].status, "B3 still queued").toBe("Queued");
      const sinkBefore = await readSink(request);
      const countB1Before = sinkBefore.filter((r: any) => r.request.batchBlockId === b1.id).length;
      const countB3Before = sinkBefore.filter((r: any) => r.request.batchBlockId === b3.id).length;

      // Resume: incomplete only, then Generate full.
      const resume = await request.post(`${TL}/projects/${pid}/scenes/${sid}/cancel`, {
        data: { action: "resume_incomplete_only" },
      });
      expect(resume.ok()).toBeTruthy();
      const gen = await request.post(`${TL}/projects/${pid}/scenes/${sid}/generate`, { data: { scope: "full" } });
      expect(gen.ok()).toBeTruthy();

      const sinkAfter = await readSink(request);
      const countB1After = sinkAfter.filter((r: any) => r.request.batchBlockId === b1.id).length;
      const countB2After = sinkAfter.filter((r: any) => r.request.batchBlockId === b2.id).length;
      const countB3After = sinkAfter.filter((r: any) => r.request.batchBlockId === b3.id).length;
      expect(countB1After, "Batch 1 (approved) never resubmitted").toBe(countB1Before);
      expect(countB2After, "Batch 2 (interrupted) resubmitted").toBeGreaterThan(1);
      expect(countB3After, "Batch 3 (queued) not submitted again — waits its turn").toBe(countB3Before);

      m = await getMaster(request, pid, sid);
      byId = Object.fromEntries(m.batchBlocks.map((b: any) => [b.id, b]));
      expect(byId[b2.id].status).toBe("Generating");
      expect(byId[b3.id].status).toBe("Queued");
      expect(byId[b1.id].approvedClip?.assetId, "Batch 1 output intact").toBe("cert-i-out-1");
      writeArtifact("I-resume-wiring.json", { countB1After, countB2After, countB3After });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("J. scale certification: 10/25/50/100 batches + 101st insertion + delete (no cap)", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    const { pid, sid } = await newScene(request, "WiringCert J");
    try {
      const tiers = [10, 25, 50, 100];
      const evidence: Array<{ tier: number; uniqueIds: number; persisted: boolean }> = [];
      for (const tier of tiers) {
        let m = await getMaster(request, pid, sid);
        while (m.batchBlocks.length < tier) {
          await addBatch(request, pid, sid, 2);
          m = await getMaster(request, pid, sid);
        }
        const ids = m.batchBlocks.map((b: any) => b.id);
        expect(new Set(ids).size, `tier ${tier}: unique ids`).toBe(ids.length);
        // save/reload persistence at each tier
        const m2 = await getMaster(request, pid, sid);
        expect(m2.batchBlocks.map((b: any) => b.id)).toEqual(ids);
        evidence.push({ tier, uniqueIds: ids.length, persisted: true });
      }
      // Batch 101 insertion — no product-defined cap.
      const b101 = await addBatch(request, pid, sid, 2);
      let m = await getMaster(request, pid, sid);
      expect(m.batchBlocks.length, "batch 101 accepted").toBe(101);
      // Delete one — state integrity maintained.
      const del = await request.delete(`${TL}/projects/${pid}/scenes/${sid}/batches/${b101.id}`);
      expect(del.ok()).toBeTruthy();
      m = await getMaster(request, pid, sid);
      expect(m.batchBlocks.length).toBe(100);
      expect(m.batchBlocks.some((b: any) => b.id === b101.id), "deleted batch gone").toBeFalsy();
      expect(new Set(m.batchBlocks.map((b: any) => b.id)).size, "ids still unique").toBe(100);
      writeArtifact("J-scale-certification.json", { tiers: evidence, batch101: "accepted", afterDelete: 100 });
    } finally {
      await deleteProject(request, pid);
    }
  });

  // -----------------------------------------------------------------------
  // Extended gates (Timeline Full Audit milestone): fingerprint contract (Q),
  // developer export artifacts (S), Timeline console cleanliness (T).
  // Q/S require the Beta API started with ADEPT_TIMELINE_WORKFLOW_EXPORT=1.
  // -----------------------------------------------------------------------

  async function exportBatchWorkflow(request: APIRequestContext, pid: string, sid: string, batchId: string) {
    const r = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches/${batchId}/workflow-export`);
    return r;
  }

  async function probeExportEnabled(request: APIRequestContext): Promise<boolean> {
    // Enabled-but-missing batch → 422/404 with structured detail; disabled →
    // plain 404 "Not found". Probe with a deterministic bogus id.
    const r = await request.post(`${TL}/projects/00000000-0000-0000-0000-000000000000/scenes/x/batches/y/workflow-export`);
    if (r.status() === 404) {
      const body = await r.json().catch(() => ({}));
      return !(body && body.detail === "Not found");
    }
    return r.status() !== 404;
  }

  test("Q. fingerprint stability: per-job variation never drifts the certified topology", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    const EXPORT_ON = await probeExportEnabled(request);
    test.skip(!EXPORT_ON, "workflow export disabled — restart Beta API with ADEPT_TIMELINE_WORKFLOW_EXPORT=1");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert Q");
    try {
      // Pin the scene engine to LTX so the export walks the real LTX graph path.
      const eng = await request.patch(`${API}/api/projects/${pid}/scenes/${sid}`, { data: { engine: "ltx" } });
      expect(eng.ok(), "pin scene engine to ltx").toBeTruthy();

      let m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 8);
      const img1 = await uploadImage(request, pid, "cert-q-start-1", PNG_RED);
      const img2 = await uploadImage(request, pid, "cert-q-start-2", PNG_BLUE);
      await configBatch(request, pid, sid, b1.id, {
        prompt: "Q-ALPHA: slow push-in on a rain-lit window",
        plannedDuration: 5,
        startImageAssetId: img1,
        generatorId: "ltx-local",
      });
      await configBatch(request, pid, sid, b2.id, {
        prompt: "Q-BETA: completely different prompt — aerial orbit over neon city",
        plannedDuration: 8,
        startImageAssetId: img2,
        generatorId: "ltx-local",
      });

      const e1 = await exportBatchWorkflow(request, pid, sid, b1.id);
      expect(e1.ok(), `export b1: ${await e1.text()}`).toBeTruthy();
      const e2 = await exportBatchWorkflow(request, pid, sid, b2.id);
      expect(e2.ok(), `export b2: ${await e2.text()}`).toBeTruthy();
      const r1 = await e1.json();
      const r2 = await e2.json();

      expect(r1.topologyMatch, "b1 topology matches certified").toBe(true);
      expect(r2.topologyMatch, "b2 topology matches certified").toBe(true);
      expect(r1.bindingsValid, "b1 bindings valid").toBe(true);
      expect(r2.bindingsValid, "b2 bindings valid").toBe(true);

      const fp1 = JSON.parse(fs.readFileSync(r1.artifacts.fingerprints, "utf8"));
      const fp2 = JSON.parse(fs.readFileSync(r2.artifacts.fingerprints, "utf8"));
      expect(fp1.topologyHash.certified, "certified topologyHash present (gate is not vacuous)").toBeTruthy();
      expect(fp1.topologyHash.actual, "b1 actual == certified").toBe(fp1.topologyHash.certified);
      expect(fp2.topologyHash.actual, "b2 actual == certified").toBe(fp2.topologyHash.certified);
      expect(fp1.topologyHash.actual, "identical topology across different jobs").toBe(fp2.topologyHash.actual);

      // The jobs genuinely differed — bindings prove the variation existed.
      const b1bind = JSON.parse(fs.readFileSync(r1.artifacts.bindings, "utf8"));
      const b2bind = JSON.parse(fs.readFileSync(r2.artifacts.bindings, "utf8"));
      expect(JSON.stringify(b1bind.bindings)).not.toBe(JSON.stringify(b2bind.bindings));
      expect(fp1.paramMapping.framesSnapped, "different durations → different frame counts").not.toBe(
        fp2.paramMapping.framesSnapped,
      );

      // Export never queues/executes: cert sink stays empty.
      const sink = await readSink(request);
      expect(sink.length, "export submitted nothing to the provider boundary").toBe(0);
      writeArtifact("Q-fingerprint-stability.json", {
        certifiedTopology: fp1.topologyHash.certified,
        b1: { topologyMatch: r1.topologyMatch, bindingsValid: r1.bindingsValid, frames: fp1.paramMapping.framesSnapped },
        b2: { topologyMatch: r2.topologyMatch, bindingsValid: r2.bindingsValid, frames: fp2.paramMapping.framesSnapped },
      });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("S. developer export writes complete inspection artifacts", async ({ request }) => {
    test.skip(!STUB_ON, "cert stub required");
    const EXPORT_ON = await probeExportEnabled(request);
    test.skip(!EXPORT_ON, "workflow export disabled — restart Beta API with ADEPT_TIMELINE_WORKFLOW_EXPORT=1");
    const { pid, sid } = await newScene(request, "WiringCert S");
    try {
      const eng = await request.patch(`${API}/api/projects/${pid}/scenes/${sid}`, { data: { engine: "ltx" } });
      expect(eng.ok()).toBeTruthy();
      const m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      const img = await uploadImage(request, pid, "cert-s-start", PNG_RED);
      await configBatch(request, pid, sid, b1.id, {
        prompt: "S: artifact completeness check",
        plannedDuration: 5,
        startImageAssetId: img,
        generatorId: "ltx-local",
      });

      const e = await exportBatchWorkflow(request, pid, sid, b1.id);
      expect(e.ok(), `export: ${await e.text()}`).toBeTruthy();
      const body = await e.json();
      for (const key of ["workflow", "api", "bindings", "fingerprints"]) {
        expect(body.artifacts[key], `artifact path present: ${key}`).toBeTruthy();
        expect(fs.existsSync(body.artifacts[key]), `artifact on disk: ${key}`).toBeTruthy();
      }
      const fp = JSON.parse(fs.readFileSync(body.artifacts.fingerprints, "utf8"));
      expect(fp.topologyMatch).toBe(true);
      expect(fp.bindingsValid).toBe(true);
      expect(fp.paramMapping.executionSnapshotId).toBeTruthy();
      expect(fp.workflowKey).toContain("ltx");
      const bindings = JSON.parse(fs.readFileSync(body.artifacts.bindings, "utf8"));
      expect(bindings.loadImageReference.uploadedInExportMode, "export never uploads to ComfyUI").toBe(false);
      const apiGraph = JSON.parse(fs.readFileSync(body.artifacts.api, "utf8"));
      expect(Object.keys(apiGraph).length, "api graph has nodes").toBeGreaterThan(3);
      writeArtifact("S-export-artifacts.json", { artifacts: body.artifacts, topologyMatch: fp.topologyMatch });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("T. Timeline UI: zero Timeline-critical console errors or failed requests", async ({ page, request }) => {
    test.skip(!STUB_ON, "cert stub required");
    const { pid, sid } = await newScene(request, "WiringCert T");
    try {
      const m = await getMaster(request, pid, sid);
      const b1 = m.batchBlocks[0];
      await configBatch(request, pid, sid, b1.id, { prompt: "T: console cleanliness", plannedDuration: 5 });

      const TIMELINE_CRITICAL = [
        /\/api\/director-timeline/i,
        /\/api\/projects\/[^/]+\/scenes/i,
        /\/api\/projects\/[^/]+\/jobs/i,
        /\/api\/projects\/[^/]+\/preview\/stream/i,
        /\/api\/assets/i,
        /\/api\/codirector\/timeline/i,
        /\/api\/codirector\/context/i,
      ];
      const consoleErrors: string[] = [];
      const failedRequests: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() !== "error") return;
        const loc = msg.location()?.url || "";
        const text = msg.text();
        // Resource-load console errors carry the failing URL in location.
        if (TIMELINE_CRITICAL.some((p) => p.test(loc))) {
          consoleErrors.push(`${text.slice(0, 200)} @ ${loc}`);
        }
      });
      page.on("requestfailed", (req) => {
        const url = req.url();
        const failure = req.failure()?.errorText || "";
        // ERR_ABORTED is ordinary React Query/SSE cancellation on navigation.
        if (failure.includes("ERR_ABORTED")) return;
        if (TIMELINE_CRITICAL.some((p) => p.test(url))) {
          failedRequests.push(`${failure} ${url.slice(0, 200)}`);
        }
      });
      page.on("response", (res) => {
        const url = res.url();
        if (res.status() >= 400 && TIMELINE_CRITICAL.some((p) => p.test(url))) {
          failedRequests.push(`HTTP ${res.status()} ${url.slice(0, 200)}`);
        }
      });

      await gotoTimeline(page, pid);
      await page.getByTestId(`timeline-batch-${b1.id}`).click();
      await expect(page.getByTestId("timeline-batch-generator")).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(4000); // let pollers/SSE fire

      expect(failedRequests, `Timeline-critical request failures: ${failedRequests.join(" | ")}`).toEqual([]);
      expect(consoleErrors, `Timeline-critical console errors: ${consoleErrors.join(" | ")}`).toEqual([]);
      writeArtifact("T-console-cleanliness.json", { consoleErrors, failedRequests });
    } finally {
      await deleteProject(request, pid);
    }
  });

  test("U. failed overlay dismiss persists across reload; a NEW failure re-shows", async ({ page, request }) => {
    test.skip(!STUB_ON, "cert stub required");
    await resetCert(request);
    const { pid, sid } = await newScene(request, "WiringCert U");
    try {
      // Cert-seeded terminal Job rows drive the REAL monitor failure path
      // (jobs table → composition → overlay). The stub adapter never creates
      // Job rows by design, so generation alone cannot reach this overlay.
      const seed = async (message: string) => {
        const r = await request.post(`${TL}/cert/seed-failed-job`, { data: { projectId: pid, sceneId: sid, message } });
        expect(r.ok(), "seed failed job").toBeTruthy();
        return (await r.json()).jobId as string;
      };

      const jobId = await seed("simulated failure for dismiss cert");

      // UI: the failed overlay appears with a Dismiss control.
      await gotoTimeline(page, pid);
      await expect(page.getByTestId("live-preview-failed-overlay")).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("live-preview-dismiss-failure")).toBeVisible();

      // Dismiss → overlay clears and the acknowledgment persists on the master.
      await page.getByTestId("live-preview-dismiss-failure").click();
      await expect(page.getByTestId("live-preview-failed-overlay")).toHaveCount(0, { timeout: 15_000 });
      await expect
        .poll(
          async () => ((await getMaster(request, pid, sid)).dismissedFailureJobIds ?? []).includes(jobId),
          { timeout: 10_000, intervals: [500, 1_000] },
        )
        .toBe(true);

      // Reload → still dismissed (server-persisted, not session state).
      await page.reload();
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 30_000 });
      await page.waitForTimeout(4_000); // let the jobs poller land
      await expect(page.getByTestId("live-preview-failed-overlay")).toHaveCount(0);

      // A NEW failure (different job id) re-shows the overlay.
      const jobId2 = await seed("second simulated failure");
      expect(jobId2).not.toBe(jobId);
      await expect(page.getByTestId("live-preview-failed-overlay")).toBeVisible({ timeout: 30_000 });

      writeArtifact("U-dismiss-failure.json", {
        jobId,
        jobId2,
        dismissPersistedAcrossReload: true,
        newFailureReshowsOverlay: true,
      });
    } finally {
      await deleteProject(request, pid);
    }
  });
});
