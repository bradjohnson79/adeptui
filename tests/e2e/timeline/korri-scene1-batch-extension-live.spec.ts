/**
 * Live Korri Scene 1 — Batch 1 + Batch 2 sequential play + reload.
 * Reuses project beffd3d8-791d-4adf-9c4d-681ec9d4efb0. Never POST /api/projects.
 */
import { expect, test, type Page } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const SCENE_ID = "1f46b621-46f9-4b7e-8273-202a49e1ca7c";
const B1_ID = "bb_2e4f42cb44fd";
const B2_ID = "bb_581d6daed83e";
const B1_ASSET = "cc4c6bb1-20c6-4be5-a138-2f6f817b6faa";
const B2_ASSET = "81333962-7488-45ec-804f-0d2cae1d5717";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const STILLS = path.join("artifacts", "korri-scene1-batch-extension");

async function openTimeline(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${SCENE_ID}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-playhead")).toBeVisible({ timeout: 30_000 });
}

function playheadSec(page: Page): Promise<number> {
  return page.getByTestId("timeline-playhead").getAttribute("data-playhead").then((v) => Number(v || 0));
}

test.describe("Korri Scene 1 batch extension live", () => {
  test("two LTX batches play as one scene and survive reload", async ({ page, request }) => {
    await mkdir(STILLS, { recursive: true });

    const masterRes = await request.get(`${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${SCENE_ID}/master`);
    expect(masterRes.ok(), await masterRes.text()).toBeTruthy();
    const master = (await masterRes.json()).master;
    const batches = master.batchBlocks || [];
    expect(batches.map((b: { id: string }) => b.id)).toEqual([B1_ID, B2_ID]);
    expect(batches[0].status).toBe("Approved");
    expect(batches[1].status).toBe("Approved");
    // generatorId is persisted historical record (batches were authored when
    // LTX 2.3 "ltx-local" was live). Coverage intent: both batches share one
    // consistent generator — do not pin the retired id.
    expect(batches[0].generatorId).toBeTruthy();
    expect(batches[1].generatorId).toBe(batches[0].generatorId);
    expect(batches[1].approvedClip?.assetId).toBe(B2_ASSET);
    const incoming = (batches[1].candidateVersions || []).find((c: { approved?: boolean }) => c.approved);
    expect(incoming?.incomingContinuity?.continuityStrategy).toBe("last_frame_i2v");
    expect(incoming?.incomingContinuity?.sourceBatchId).toBe(B1_ID);

    await openTimeline(page);
    await expect(page.getByTestId(`timeline-batch-${B1_ID}`)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId(`timeline-batch-${B2_ID}`)).toBeVisible();
    await page.screenshot({ path: path.join(STILLS, "01-two-batches.png"), fullPage: true });

    const play = page.getByTestId("timeline-transport-play");
    await expect(play).toBeVisible();
    await play.click();

    await expect
      .poll(async () => playheadSec(page), { timeout: 20_000 })
      .toBeGreaterThan(5.15);

    const preview = page.getByTestId("live-preview-video");
    await expect(preview).toBeVisible({ timeout: 15_000 });
    const srcAtB2 = await preview.getAttribute("src");
    expect(srcAtB2 || "").toMatch(new RegExp(`${B2_ASSET}|scene_0_41bce89b\\.mp4`));
    const headAtB2 = await playheadSec(page);
    expect(headAtB2).toBeGreaterThan(5);
    expect(headAtB2).toBeLessThanOrEqual(10.05);

    await writeFile(
      path.join(STILLS, "play-through.json"),
      JSON.stringify({ playheadSec: headAtB2, previewSrc: srcAtB2 }, null, 2),
      "utf8",
    );
    await page.screenshot({ path: path.join(STILLS, "02-playhead-in-batch2.png"), fullPage: true });

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId(`timeline-batch-${B1_ID}`)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId(`timeline-batch-${B2_ID}`)).toBeVisible();

    const afterReload = await request.get(`${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${SCENE_ID}/master`);
    const reloaded = (await afterReload.json()).master;
    const clipsRes = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${SCENE_ID}`);
    const scene = await clipsRes.json();
    const director = JSON.parse(scene.director_json || "{}");
    const clips = director.video_clips || [];
    expect(clips).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: `bbclip_${B1_ID}`, asset_id: B1_ASSET, start: 0, length: 5 }),
        expect.objectContaining({ id: `bbclip_${B2_ID}`, asset_id: B2_ASSET, start: 5, length: 5 }),
      ]),
    );
    expect(reloaded.batchBlocks).toHaveLength(2);
    expect(reloaded.batchBlocks[0].status).toBe("Approved");
    expect(reloaded.batchBlocks[1].status).toBe("Approved");

    await page.screenshot({ path: path.join(STILLS, "03-after-reload.png"), fullPage: true });
    await writeFile(
      path.join(STILLS, "reload.json"),
      JSON.stringify(
        {
          batches: reloaded.batchBlocks.map((b: { id: string; status: string; approvedClip?: { assetId?: string } }) => ({
            id: b.id,
            status: b.status,
            assetId: b.approvedClip?.assetId,
          })),
          videoClips: clips,
        },
        null,
        2,
      ),
      "utf8",
    );
  });
});
