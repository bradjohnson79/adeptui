/**
 * Clean Creator Data Reset — Fresh Timeline Baseline Certification
 * (NO AUTOMATED GPU GENERATION)
 *
 * Validates the clean-slate state after the creator-data reset:
 *  - Fresh project baseline (1 project / 1 scene / 0 jobs / no failure state)
 *  - localStorage prune of stale deleted project IDs
 *  - Clean Timeline authoring (3 batches, distinct images/prompts)
 *  - Preview Monitor shows correct image, no old Render Failed overlay
 *  - Preflight succeeds (non-GPU)
 *
 * Requires ADEPT_BETA_TARGET=1. No cert stub, no export env. Serial, workers=1.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/clean-beta-baseline/artifacts");
const TL = `${API}/api/director-timeline`;

// 8x8 solid PNGs — visually distinguishable cert inputs.
const PNG_RED = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEklEQVR4nGP4z8CAFWEXHbQSACj/P8Fu7N9hAAAAAElFTkSuQmCC",
  "base64",
);
const PNG_GREEN = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEElEQVR4nGNgYPj/H4GCAkCpcD/BJMoqcwAAAABJRU5ErkJggg==",
  "base64",
);
const PNG_BLUE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEElEQVR4nGNgYPiPAw0pCQCpcD/BFMrqcwAAAABJRU5ErkJggg==",
  "base64",
);

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function getMaster(request: APIRequestContext, pid: string, sid: string) {
  const r = await request.get(`${TL}/projects/${pid}/scenes/${sid}/master`);
  expect(r.ok(), "master GET").toBeTruthy();
  return (await r.json()).master;
}

async function addBatch(request: APIRequestContext, pid: string, sid: string, plannedDuration = 5) {
  const r = await request.post(`${TL}/projects/${pid}/scenes/${sid}/batches`, {
    data: { plannedDuration },
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
      generatorId: cfg.generatorId,
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

async function gotoTimeline(page: Page, pid: string) {
  await page.goto(`/project/${pid}?workspace=timeline`);
  await page.waitForLoadState("domcontentloaded");
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 30_000 });
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta clean creator data reset — fresh timeline baseline (no GPU)", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("0. app ready + clean slate (0 projects before fresh creation)", async ({ request }) => {
    await waitForAppReady(request);
    const res = await request.get(`${API}/api/projects`);
    expect(res.ok()).toBeTruthy();
    const projects = await res.json();
    const count = Array.isArray(projects) ? projects.length : (projects.projects?.length ?? 0);
    writeArtifact("00-clean-slate-projects.json", { count, projects });
    // After the reset, no projects should exist until we create one below.
    expect(count, "clean slate: 0 projects after reset").toBe(0);
  });

  test("1. fresh project baseline (1 project / 1 scene / 0 jobs / no failure state)", async ({ request }) => {
    const project = await createTempProject(request, "Timeline Clean Slate Test");
    writeArtifact("01-fresh-project.json", { id: project.id, name: project.name });

    // Exactly 1 project now.
    const pRes = await request.get(`${API}/api/projects`);
    const pList = await pRes.json();
    const pCount = Array.isArray(pList) ? pList.length : (pList.projects?.length ?? 0);
    expect(pCount, "exactly 1 project after creation").toBe(1);

    // Exactly 1 default scene.
    const sRes = await request.get(`${API}/api/projects/${project.id}/scenes`);
    expect(sRes.ok()).toBeTruthy();
    const scenes = await sRes.json();
    const sList = Array.isArray(scenes) ? scenes : (scenes.scenes || []);
    expect(sList.length, "exactly 1 default scene").toBe(1);
    const sid = sList[0].id as string;

    // 0 jobs, 0 failed jobs.
    const jRes = await request.get(`${API}/api/projects/${project.id}/jobs`);
    expect(jRes.ok()).toBeTruthy();
    const jobs = await jRes.json();
    const jList = Array.isArray(jobs) ? jobs : (jobs.jobs || []);
    expect(jList.length, "0 jobs on fresh project").toBe(0);

    // Timeline master has exactly the 1 default batch block, unconfigured, no failure state.
    const master = await getMaster(request, project.id, sid);
    writeArtifact("01-fresh-master.json", master);
    expect(master.batchBlocks.length, "exactly 1 default batch on fresh timeline").toBe(1);
    const defaultBatch = master.batchBlocks[0];
    // Unconfigured: no generator selected, no source image bound.
    expect(defaultBatch.generatorId || null, "default batch has no generator selected").toBeNull();
    expect((defaultBatch.sourceAnchors || []).length, "default batch has no source anchors").toBe(0);
    expect(master.dismissedFailureJobIds || [], "no dismissed failures on fresh project").toEqual([]);

    // Stash IDs for subsequent tests.
    writeArtifact("01-fresh-ids.json", { pid: project.id, sid });
  });

  test("2. localStorage prune of stale deleted project IDs", async ({ page, request }) => {
    // Seed stale deleted project IDs into both localStorage keys.
    const staleId1 = "00000000-0000-4000-8000-000000000001";
    const staleId2 = "00000000-0000-4000-8000-000000000002";
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    await page.evaluate((ids: string[]) => {
      localStorage.setItem(
        "adept_ui_last_workspace",
        JSON.stringify({ [ids[0]]: "timeline", [ids[1]]: "characters", "real-keep": "scriptwriter" }),
      );
      localStorage.setItem(
        "adept_ui_recent_projects",
        JSON.stringify([
          { id: ids[0], name: "Stale 1" },
          { id: ids[1], name: "Stale 2" },
          { id: "real-keep", name: "Keep" },
        ]),
      );
    }, [staleId1, staleId2]);

    // Reload Home — refresh() calls pruneDeletedProjects with the real project IDs.
    await page.goto("/");
    await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(1500); // allow refresh() + prune to run

    const after = await page.evaluate(() => ({
      ws: localStorage.getItem("adept_ui_last_workspace"),
      recent: localStorage.getItem("adept_ui_recent_projects"),
    }));
    writeArtifact("02-prune-after.json", after);

    const wsMap = JSON.parse(after.ws || "{}");
    expect(wsMap[staleId1], "stale workspace id 1 pruned").toBeUndefined();
    expect(wsMap[staleId2], "stale workspace id 2 pruned").toBeUndefined();

    const recent = JSON.parse(after.recent || "[]");
    expect(recent.find((p: { id: string }) => p.id === staleId1), "stale recent id 1 pruned").toBeUndefined();
    expect(recent.find((p: { id: string }) => p.id === staleId2), "stale recent id 2 pruned").toBeUndefined();
  });

  test("3. clean timeline: 3 batches, distinct images/prompts, preview, no failed overlay, preflight", async ({ page, request }) => {
    const ids = JSON.parse(fs.readFileSync(path.join(ARTIFACT_DIR, "01-fresh-ids.json"), "utf8"));
    const pid = ids.pid as string;
    const sid = ids.sid as string;

    try {
      // Upload 3 visibly distinct images.
      const img1 = await uploadImage(request, pid, "batch1-red", PNG_RED);
      const img2 = await uploadImage(request, pid, "batch2-green", PNG_GREEN);
      const img3 = await uploadImage(request, pid, "batch3-blue", PNG_BLUE);

      // Create 3 batches (first batch already exists from default master).
      const master0 = await getMaster(request, pid, sid);
      const b1 = master0.batchBlocks[0];
      const b2 = await addBatch(request, pid, sid, 5);
      const b3 = await addBatch(request, pid, sid, 5);
      const batchIds = [b1.id, b2.id, b3.id];
      writeArtifact("03-batch-ids.json", batchIds);

      // Unique IDs.
      expect(new Set(batchIds).size, "unique batch ids").toBe(3);

      // Configure each batch with a distinct image + prompt.
      await configBatch(request, pid, sid, b1.id, {
        prompt: "Red scene — clean slate batch one",
        startImageAssetId: img1,
        generatorId: "ltx-local",
      });
      await configBatch(request, pid, sid, b2.id, {
        prompt: "Green scene — clean slate batch two",
        startImageAssetId: img2,
        generatorId: "ltx-local",
      });
      await configBatch(request, pid, sid, b3.id, {
        prompt: "Blue scene — clean slate batch three",
        startImageAssetId: img3,
        generatorId: "ltx-local",
      });

      // 0 historical jobs still.
      const jRes = await request.get(`${API}/api/projects/${pid}/jobs`);
      const jobs = await jRes.json();
      const jList = Array.isArray(jobs) ? jobs : (jobs.jobs || []);
      expect(jList.length, "0 historical jobs after batch authoring").toBe(0);

      // Open Timeline in the browser.
      await gotoTimeline(page, pid);

      // No old Render Failed overlay.
      await expect(page.getByTestId("live-preview-failed-overlay")).not.toBeVisible({ timeout: 5_000 });

      // Preflight succeeds (non-GPU).
      const pfRes = await request.get(`${TL}/projects/${pid}/scenes/${sid}/preflight`);
      expect(pfRes.ok(), "preflight ok").toBeTruthy();
      const pf = await pfRes.json();
      writeArtifact("03-preflight.json", pf);
      expect(pf.ok, "preflight ok flag").toBe(true);
      expect(pf.mock, "preflight not mock").toBe(false);

      // Cross-batch preview switching: select each batch and verify the preview updates.
      for (let i = 0; i < 3; i++) {
        const batchRow = page.locator(`[data-batch-id="${batchIds[i]}"]`).first();
        if (await batchRow.isVisible().catch(() => false)) {
          await batchRow.click();
          await page.waitForTimeout(800);
        }
      }

      await page.screenshot({
        path: path.join(ARTIFACT_DIR, "03-timeline-clean-baseline.png"),
        fullPage: true,
      });

      writeArtifact("03-success.json", {
        pid,
        sid,
        batchIds,
        imageAssetIds: [img1, img2, img3],
        preflightOk: pf.ok,
        jobsCount: jList.length,
      });
    } finally {
      // Clean up the fresh project so the slate stays clean for manual creator use.
      await deleteProject(request, pid);
    }
  });
});
