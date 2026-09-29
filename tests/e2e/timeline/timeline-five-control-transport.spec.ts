/**
 * Timeline five-control transport + scene-switch stability.
 * Reuses Korri Anadriya. Never POST /api/projects. Never add/remove batches.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const WALK_ID = process.env.ADEPT_SCENE_ID || "b5282a4c-07eb-40db-9d5b-1512eac74dca";
const SCENE1_ID = "1f46b621-46f9-4b7e-8273-202a49e1ca7c";
const WALK_NAME = "Venture Corridor Walk";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

type MasterBatch = {
  id: string;
  order?: number;
  duration?: { plannedDuration?: number | null } | null;
};

function boardFromMaster(master: { batchBlocks?: MasterBatch[] } | null | undefined, fallback = 0) {
  const batches = [...(master?.batchBlocks || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  const sum = batches.reduce((total, batch) => total + Math.max(0, Number(batch.duration?.plannedDuration || 0)), 0);
  return sum > 0 ? sum : fallback;
}

function windowsFromMaster(master: { batchBlocks?: MasterBatch[] } | null | undefined) {
  const windows: Array<{ id: string; start: number; end: number }> = [];
  let cursor = 0;
  const batches = [...(master?.batchBlocks || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  for (const batch of batches) {
    const length = Math.max(0.1, Number(batch.duration?.plannedDuration || 0));
    windows.push({ id: batch.id, start: cursor, end: cursor + length });
    cursor += length;
  }
  return windows;
}

async function getJson(request: APIRequestContext, path: string) {
  const res = await request.get(`${API}${path}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function getMaster(request: APIRequestContext, sceneId: string) {
  const body = await getJson(request, `/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`);
  return body.master as { batchBlocks?: MasterBatch[]; sceneGeneratorId?: string | null };
}

async function waitForTimeline(page: Page) {
  await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-transport-scene-start")).toBeVisible();
  await expect(page.getByTestId("timeline-transport-scene-end")).toBeVisible();
}

async function openLeftDrawer(page: Page) {
  const handle = page.getByTestId("timeline-drawer-left-toggle");
  await expect(handle).toBeVisible({ timeout: 20_000 });
  if ((await handle.getAttribute("aria-expanded")) !== "true") {
    const box = await handle.boundingBox();
    if (box) await handle.click({ position: { x: Math.max(2, box.width / 2), y: 16 } });
    else await handle.click();
  }
  await expect(handle).toHaveAttribute("aria-expanded", "true", { timeout: 10_000 });
}

async function selectSceneFromDrawer(page: Page, sceneId: string) {
  await openLeftDrawer(page);
  const block = page.getByTestId(`scene-block-${sceneId}`);
  await expect(block).toBeAttached({ timeout: 30_000 });
  await block.evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
  await block.click();
}

async function expectPlayheadSec(page: Page, expected: number, tolerance = 0.12) {
  await expect
    .poll(async () => Math.abs(Number((await page.getByTestId("timeline-playhead").getAttribute("data-playhead")) || 0) - expected), {
      timeout: 10_000,
    })
    .toBeLessThanOrEqual(tolerance);
  const preview = Number((await page.getByTestId("live-preview-monitor").getAttribute("data-playhead")) || 0);
  expect(Math.abs(preview - expected), "Preview Monitor shares the Timeline playhead").toBeLessThanOrEqual(tolerance + 0.08);
  const transportHead = Number((await page.getByTestId("timeline-transport").getAttribute("data-playhead")) || 0);
  expect(Math.abs(transportHead - expected), "Transport cluster shares the Timeline playhead").toBeLessThanOrEqual(tolerance + 0.08);
}

async function waitForTransportScene(page: Page, sceneId: string, sceneEnd: number, tolerance = 0.15) {
  const transport = page.getByTestId("timeline-transport");
  await expect(transport).toHaveAttribute("data-scene-id", sceneId, { timeout: 20_000 });
  await expect
    .poll(async () => Number((await transport.getAttribute("data-scene-end")) || -1), { timeout: 20_000 })
    .toBeCloseTo(sceneEnd, 1);
  const end = Number((await transport.getAttribute("data-scene-end")) || 0);
  expect(Math.abs(end - sceneEnd)).toBeLessThanOrEqual(tolerance);
}

async function readPlayingAudio(page: Page) {
  return page.evaluate(() => {
    const host = document.querySelector('[data-testid="timeline-audio-playback"]');
    const live = host ? Array.from(host.querySelectorAll("audio")).filter((audio) => !audio.paused) : [];
    return {
      count: live.length,
      labels: live.map((audio) => audio.getAttribute("data-label") || ""),
      kinds: live.map((audio) => audio.getAttribute("data-kind") || ""),
      times: live.map((audio) => audio.currentTime),
    };
  });
}

test.describe("Timeline five-control transport + scene-switch stability", () => {
  test("multi-batch Scene 1, Walk control case, seek sync, and 20-switch stress", async ({ page, request }) => {
    test.setTimeout(240_000);

    const scene1Master = await getMaster(request, SCENE1_ID);
    const walkMaster = await getMaster(request, WALK_ID);
    const scene1Windows = windowsFromMaster(scene1Master);
    const walkWindows = windowsFromMaster(walkMaster);
    const scene1End = boardFromMaster(scene1Master);
    const walkEnd = boardFromMaster(walkMaster, 8);
    expect(scene1Windows.length, "Scene 1 must stay multi-batch").toBeGreaterThanOrEqual(3);
    expect(walkWindows.length, "Walk is the one-batch control").toBe(1);
    expect(scene1End).toBeGreaterThan(walkEnd + 1);
    expect(scene1End, "Scene End is the 25s board clock, not Scene 1 duration_sec 20").toBe(25);
    expect(scene1End).not.toBe(20);
    const mid = scene1Windows[Math.floor(scene1Windows.length / 2)];
    expect(mid.start).toBeGreaterThan(0);
    expect(mid.end).toBeLessThan(scene1End - 0.05);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/project/${PROJECT_ID}?workspace=timeline&sceneId=${SCENE1_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await waitForTimeline(page);
    await expect(page.getByRole("heading", { name: /Scene 1/i, level: 2 })).toBeVisible({ timeout: 30_000 });
    await waitForTransportScene(page, SCENE1_ID, scene1End);
    await openLeftDrawer(page);
    await page.getByTestId(`scene-overflow-${WALK_ID}`).click();
    await expect(page.getByTestId("scene-menu-rename")).toBeVisible();
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", SCENE1_ID);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("scene-menu-rename")).toHaveCount(0);

    const shell = page.getByTestId("timeline-editor-shell");
    await shell.evaluate((el) => el.setAttribute("data-stability-marker", "keep"));
    const toolbarBefore = await page.getByTestId("timeline-toolbar").boundingBox();
    const transport = page.getByTestId("timeline-transport");
    const buttons = transport.locator("button");
    await expect(buttons).toHaveCount(5);
    await expect(page.getByTestId("timeline-transport-scene-start")).toHaveAttribute("aria-label", "Go to Scene Start");
    await expect(page.getByTestId("timeline-transport-in")).toHaveAttribute("aria-label", "Go to Batch In");
    await expect(page.getByTestId("timeline-transport-play")).toHaveAttribute("aria-label", "Play Timeline");
    await expect(page.getByTestId("timeline-transport-out")).toHaveAttribute("aria-label", "Go to Batch Out");
    await expect(page.getByTestId("timeline-transport-scene-end")).toHaveAttribute("aria-label", "Go to Scene End");
    await expect(page.getByTestId("timeline-transport-pause")).toHaveCount(0);

    const startBox = await page.getByTestId("timeline-transport-scene-start").boundingBox();
    const inBox = await page.getByTestId("timeline-transport-in").boundingBox();
    const playBox = await page.getByTestId("timeline-transport-play").boundingBox();
    const outBox = await page.getByTestId("timeline-transport-out").boundingBox();
    const endBox = await page.getByTestId("timeline-transport-scene-end").boundingBox();
    expect(startBox && inBox && playBox && outBox && endBox).toBeTruthy();
    expect(startBox!.x).toBeLessThan(inBox!.x);
    expect(inBox!.x).toBeLessThan(playBox!.x);
    expect(playBox!.x).toBeLessThan(outBox!.x);
    expect(outBox!.x).toBeLessThan(endBox!.x);
    expect(Math.abs(startBox!.y - endBox!.y)).toBeLessThan(8);

    const midBatch = page.getByTestId(`timeline-batch-${mid.id}`);
    await expect(midBatch).toBeVisible({ timeout: 30_000 });
    await midBatch.click();

    await page.getByTestId("timeline-transport-in").click();
    await expectPlayheadSec(page, mid.start);
    expect(Number((await transport.getAttribute("data-batch-in")) || 0)).toBeCloseTo(mid.start, 1);
    expect(Number((await transport.getAttribute("data-scene-start")) || -1)).toBeCloseTo(0, 1);
    expect(Number((await transport.getAttribute("data-scene-end")) || 0)).toBeCloseTo(scene1End, 1);

    await page.getByTestId("timeline-transport-out").click();
    await expectPlayheadSec(page, mid.end);
    expect(Number((await transport.getAttribute("data-batch-out")) || 0)).toBeCloseTo(mid.end, 1);
    expect(mid.end).not.toBeCloseTo(scene1End, 1);

    await page.getByTestId("timeline-transport-scene-start").click();
    await expectPlayheadSec(page, 0);
    await page.getByTestId("timeline-transport-scene-start").click();
    await expectPlayheadSec(page, 0);

    await page.getByTestId("timeline-transport-scene-end").click();
    await expectPlayheadSec(page, scene1End);
    await page.getByTestId("timeline-transport-scene-end").click();
    await expectPlayheadSec(page, scene1End);
    expect(Number((await transport.getAttribute("data-scene-end")) || 0)).not.toBe(Number((await transport.getAttribute("data-batch-out")) || 0));

    await page.getByTestId("timeline-transport-scene-start").click();
    await expectPlayheadSec(page, 0);
    await page.getByTestId("timeline-transport-play").click();
    await expect(page.getByTestId("timeline-transport-play")).toHaveAttribute("aria-pressed", "true");
    await expect
      .poll(async () => Number((await page.getByTestId("timeline-playhead").getAttribute("data-playhead")) || 0), {
        timeout: 6_000,
      })
      .toBeGreaterThan(0.2);

    await selectSceneFromDrawer(page, WALK_ID);
    await expect(page.getByRole("heading", { name: WALK_NAME, level: 2 })).toBeVisible({ timeout: 20_000 });
    await waitForTransportScene(page, WALK_ID, walkEnd);
    await expectPlayheadSec(page, 0, 0.2);
    await expect(page.getByTestId("timeline-transport-play")).toHaveAttribute("aria-pressed", "false");
    await expect.poll(async () => (await readPlayingAudio(page)).count, { timeout: 8_000 }).toBe(0);

    await page.getByTestId("timeline-transport-scene-start").click();
    await expectPlayheadSec(page, walkWindows[0].start);
    await page.getByTestId("timeline-transport-in").click();
    await expectPlayheadSec(page, walkWindows[0].start);
    await page.getByTestId("timeline-transport-out").click();
    await expectPlayheadSec(page, walkWindows[0].end);
    await page.getByTestId("timeline-transport-scene-end").click();
    await expectPlayheadSec(page, walkEnd);
    expect(Number((await transport.getAttribute("data-scene-start")) || -1)).toBeCloseTo(
      Number((await transport.getAttribute("data-batch-in")) || -2),
      1,
    );
    expect(Number((await transport.getAttribute("data-scene-end")) || -1)).toBeCloseTo(
      Number((await transport.getAttribute("data-batch-out")) || -2),
      1,
    );
    await expect(buttons).toHaveCount(5);

    await page.getByTestId("timeline-transport-scene-start").click();
    await page.getByTestId("timeline-transport-play").click();
    await expect(page.getByTestId("timeline-transport-play")).toHaveAttribute("aria-pressed", "true");
    await expect
      .poll(async () => Number((await page.getByTestId("timeline-playhead").getAttribute("data-playhead")) || 0), {
        timeout: 6_000,
      })
      .toBeGreaterThan(0.25);
    const playingAudio = await readPlayingAudio(page);
    expect(playingAudio.count, "Walk media must start with Play").toBeGreaterThan(0);

    await page.getByTestId("timeline-transport-scene-start").click();
    await expectPlayheadSec(page, 0, 0.2);
    await expect(page.getByTestId("timeline-transport-play")).toHaveAttribute("aria-pressed", "true");
    await expect
      .poll(
        async () => {
          const audio = await readPlayingAudio(page);
          return audio.times.length ? Math.max(...audio.times) : 99;
        },
        { timeout: 6_000 },
      )
      .toBeLessThan(0.45);

    await page.getByTestId("timeline-transport-scene-end").click();
    await expectPlayheadSec(page, walkEnd, 0.2);

    await selectSceneFromDrawer(page, SCENE1_ID);
    await waitForTransportScene(page, SCENE1_ID, scene1End);
    await expectPlayheadSec(page, 0, 0.2);
    await expect.poll(async () => (await readPlayingAudio(page)).count, { timeout: 8_000 }).toBe(0);

    for (let i = 0; i < 20; i += 1) {
      const target = i % 2 === 0 ? WALK_ID : SCENE1_ID;
      const end = target === WALK_ID ? walkEnd : scene1End;
      await selectSceneFromDrawer(page, target);
      await waitForTransportScene(page, target, end);
      await expectPlayheadSec(page, 0, 0.25);
      await page.getByTestId("timeline-transport-scene-end").click();
      await expectPlayheadSec(page, end, 0.25);
      await page.getByTestId("timeline-transport-scene-start").click();
      await expectPlayheadSec(page, 0, 0.25);
      expect(await shell.getAttribute("data-stability-marker")).toBe("keep");
      const staleEnd = target === WALK_ID ? scene1End : walkEnd;
      const liveEnd = Number((await transport.getAttribute("data-scene-end")) || 0);
      expect(Math.abs(liveEnd - staleEnd)).toBeGreaterThan(1);
    }

    await page.goto(`/project/${PROJECT_ID}?workspace=timeline&sceneId=${WALK_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await waitForTimeline(page);
    await waitForTransportScene(page, WALK_ID, walkEnd);
    await expect(page.getByRole("heading", { name: WALK_NAME, level: 2 })).toBeVisible();

    const toolbarAfter = await page.getByTestId("timeline-toolbar").boundingBox();
    expect(toolbarBefore && toolbarAfter).toBeTruthy();
    expect(Math.abs((toolbarAfter!.height || 0) - (toolbarBefore!.height || 0))).toBeLessThan(28);
  });
});
