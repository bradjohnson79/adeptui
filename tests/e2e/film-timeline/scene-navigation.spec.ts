import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/** Three audible clips. Playback, reorder, stitch, and preview resize share one scene. */

function makeClip(dir: string, name: string, color: string): Buffer {
  const out = join(dir, name);
  execFileSync(
    "ffmpeg",
    [
      "-y",
      "-loglevel",
      "error",
      "-f",
      "lavfi",
      "-i",
      `color=c=${color}:duration=6:size=640x360:rate=24`,
      "-f",
      "lavfi",
      "-i",
      "sine=frequency=440:duration=6",
      "-shortest",
      "-pix_fmt",
      "yuv420p",
      out,
    ],
    { stdio: "pipe" },
  );
  return readFileSync(out);
}

async function upload(request: APIRequestContext, projectId: string, file: Buffer, tag: string): Promise<string> {
  const res = await request.post(`/api/projects/${projectId}/assets`, {
    multipart: { file: { name: `${tag}.mp4`, mimeType: "video/mp4", buffer: file }, tag, kind: "video" },
  });
  expect(res.ok(), `upload ${tag}: ${res.status()}`).toBeTruthy();
  return String((await res.json()).id || "");
}

async function shotId(request: APIRequestContext, projectId: string, sceneId: string): Promise<string> {
  const film = await request.get(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}`);
  expect(film.ok()).toBeTruthy();
  const existing = ((await film.json())?.film?.shots || [])[0];
  if (existing?.id) return String(existing.id);
  const created = await request.post(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}/shots`, {
    data: { durationSec: 6, timedPrompt: "" },
  });
  expect(created.ok()).toBeTruthy();
  const body = await created.json();
  return String(body?.shot?.id || body?.film?.shots?.[0]?.id || "");
}

async function importVideo(request: APIRequestContext, projectId: string, sceneId: string, id: string, assetId: string) {
  const res = await request.post(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}/shots/${id}/import-video`, {
    data: { assetId },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function sceneTime(page: Page): Promise<number> {
  return Number(await page.getByTestId("film-timeline-playhead").getAttribute("data-scene-time"));
}

async function shotOrder(page: Page): Promise<string[]> {
  return page.getByTestId("film-timeline-batch").evaluateAll((els) => els.map((el) => el.getAttribute("data-shot-number") || ""));
}

async function videoHeight(page: Page): Promise<number> {
  return page.getByTestId("film-timeline-monitor").locator("video").evaluate((el) => Math.round(el.getBoundingClientRect().height));
}

async function nudgeDivider(page: Page, dy: number) {
  const divider = page.getByTestId("timeline-monitor-divider").first();
  await divider.scrollIntoViewIfNeeded();
  const box = await divider.boundingBox();
  expect(box).toBeTruthy();
  const x = box!.x + box!.width / 2;
  const y = box!.y + box!.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y + dy, { steps: 12 });
  await page.mouse.up();
}

test("preview resizes, clips reorder, stitch follows the track, and playback crosses shots", async ({ page, request }) => {
  test.setTimeout(180_000);
  const created = await request.post("/api/projects", { data: { name: `Scene Nav ${Date.now()}` } });
  expect(created.ok()).toBeTruthy();
  const projectId = String((await created.json()).id || "");
  const scene = await request.post(`/api/projects/${projectId}/scenes`, {
    data: { name: "Navigation Scene", engine: "auto", duration_sec: 18, prompt: "" },
  });
  expect(scene.ok()).toBeTruthy();
  const sceneId = String((await scene.json()).id || "");
  const dir = mkdtempSync(join(tmpdir(), "adept-nav-"));
  try {
    const clips = [makeClip(dir, "a.mp4", "steelblue"), makeClip(dir, "b.mp4", "darkred"), makeClip(dir, "c.mp4", "seagreen")];
    const id = await shotId(request, projectId, sceneId);
    for (let index = 0; index < clips.length; index += 1) {
      const assetId = await upload(request, projectId, clips[index], `nav-${index}`);
      await importVideo(request, projectId, sceneId, id, assetId);
    }

    await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${sceneId}`);
    await expect(page.getByTestId("film-timeline-track")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("film-timeline-monitor").locator("video")).toBeVisible();

    const video = page.getByTestId("film-timeline-monitor").locator("video");
    const fitted = await video.evaluate((el) => getComputedStyle(el).objectFit);
    expect(fitted).toBe("contain");
    const before = await videoHeight(page);
    await nudgeDivider(page, 70);
    await expect.poll(() => videoHeight(page)).toBeGreaterThan(before + 30);
    const grown = await videoHeight(page);
    const monitor = await page.getByTestId("film-timeline-monitor").evaluate((el) => Math.round(el.getBoundingClientRect().height));
    expect(Math.abs(monitor - grown)).toBeLessThan(4);
    await nudgeDivider(page, -50);
    await expect.poll(() => videoHeight(page)).toBeLessThan(grown - 24);

    const labels = await page.getByTestId("film-timeline-transport").locator("button").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
    expect(labels).toEqual(["Beginning of Scene", "Start of Batch", "Back 5 seconds", "Play", "Forward 5 seconds", "End of Batch", "End of Scene"]);

    await page.getByTestId("film-timeline-stitch").click();
    await expect(page.getByTestId("film-timeline-stitch-note")).toHaveText("Scene stitched", { timeout: 60_000 });
    await expect(video).toHaveAttribute("data-preview-source", "stitch");

    await page.getByRole("button", { name: "Beginning of Scene" }).click();
    await page.getByTestId("film-timeline-skip-forward").click();
    await page.getByTestId("film-timeline-skip-forward").click();
    await expect.poll(() => sceneTime(page)).toBeGreaterThan(9);
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 2");
    await page.getByRole("button", { name: "Beginning of Scene" }).click();
    await page.getByTestId("film-timeline-skip-forward").click();
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect.poll(() => sceneTime(page), { timeout: 8_000 }).toBeGreaterThan(6.2);
    await expect(video).toHaveAttribute("data-preview-source", "stitch");
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 2");
    const pausedAt = await sceneTime(page);
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await page.waitForTimeout(700);
    expect(Math.abs((await sceneTime(page)) - pausedAt)).toBeLessThan(0.45);
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect.poll(() => sceneTime(page), { timeout: 4_000 }).toBeGreaterThan(pausedAt + 0.4);
    await expect.poll(() => sceneTime(page), { timeout: 12_000 }).toBeGreaterThan(12.2);
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 3");
    await expect.poll(() => sceneTime(page), { timeout: 12_000 }).toBeGreaterThan(17.4);
    await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Start of Batch" }).click();
    const atBatch = await sceneTime(page);
    expect(atBatch).toBeGreaterThan(11.5);
    expect(atBatch).toBeLessThan(12.5);
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect.poll(() => sceneTime(page), { timeout: 4_000 }).toBeGreaterThan(atBatch + 0.4);
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    await page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 3" }).getByTestId("film-timeline-clip-menu").click();
    await expect(page.getByTestId("film-timeline-move-later")).toBeDisabled();
    await page.getByTestId("film-timeline-move-earlier").click();
    await expect.poll(() => shotOrder(page)).toEqual(["1", "3", "2"]);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("film-timeline-track")).toBeVisible({ timeout: 45_000 });
    await expect.poll(() => shotOrder(page)).toEqual(["1", "3", "2"]);
    const after = await request.get(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}`);
    expect(after.ok()).toBeTruthy();
    const state = ((await after.json())?.film?.shots || [])[0]?.state || {};
    expect(String(state.stitchStatus || "")).toBe("stale");
    expect(state.stitchAssetId || null).toBeFalsy();

    await page.getByRole("button", { name: "Beginning of Scene" }).click();
    await page.getByTestId("film-timeline-skip-forward").click();
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect.poll(() => sceneTime(page), { timeout: 8_000 }).toBeGreaterThan(6.2);
    await expect(page.getByTestId("film-timeline-monitor").locator("video")).toHaveAttribute("data-preview-source", "segment");
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 3");
    await page.getByRole("button", { name: "Pause", exact: true }).click();

    await page.getByTestId("film-timeline-stitch").click();
    await expect(page.getByTestId("film-timeline-stitch-note")).toHaveText("Scene stitched", { timeout: 60_000 });
    await expect(page.getByTestId("film-timeline-monitor").locator("video")).toHaveAttribute("data-preview-source", "stitch");

    await page.getByTestId("preview-video-fullscreen").click();
    await expect(page.getByTestId("preview-fs-batch-start")).toBeVisible();
    const fullscreen = await page.locator(".preview-fullscreen-controls button").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
    expect(fullscreen).toEqual([
      "Jump to Beginning",
      "Start of Batch",
      "Rewind 5 Seconds",
      "Play",
      "Forward 5 Seconds",
      "End of Batch",
      "Jump to End",
    ]);
    await page.getByTestId("preview-fs-jump-start").click();
    await expect.poll(() => sceneTime(page)).toBeLessThan(0.2);
    await page.getByTestId("preview-fs-forward-5").click();
    await expect.poll(() => sceneTime(page)).toBeGreaterThan(4.5);
    await expect(page.getByTestId("preview-fullscreen-time")).toContainText("0:05");
    await page.getByTestId("preview-fs-exit").click();
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
