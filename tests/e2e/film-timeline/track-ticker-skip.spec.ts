import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/** Long assembled scene so the Visual Track overflows and ±5s can cross a shot. */

function makeClip(dir: string, name: string, color: string): Buffer {
  const out = join(dir, name);
  execFileSync(
    "ffmpeg",
    ["-y", "-loglevel", "error", "-f", "lavfi", "-i", `color=c=${color}:duration=20:size=320x180:rate=24`, "-pix_fmt", "yuv420p", out],
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
    data: { durationSec: 20, timedPrompt: "" },
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

async function scrollLeft(page: Page): Promise<number> {
  return page.getByTestId("film-timeline-track-scroll").evaluate((el) => (el as HTMLElement).scrollLeft);
}

test("track ticker scrolls the viewport and ±5 seconds move the scene playhead", async ({ page, request }) => {
  test.setTimeout(120_000);
  const created = await request.post("/api/projects", { data: { name: `Track Ticker ${Date.now()}` } });
  expect(created.ok()).toBeTruthy();
  const projectId = String((await created.json()).id || "");
  const scene = await request.post(`/api/projects/${projectId}/scenes`, {
    data: { name: "Ticker Scene", engine: "auto", duration_sec: 60, prompt: "" },
  });
  expect(scene.ok()).toBeTruthy();
  const sceneId = String((await scene.json()).id || "");

  const dir = mkdtempSync(join(tmpdir(), "adept-ticker-"));
  try {
    const clips = [
      makeClip(dir, "a.mp4", "steelblue"),
      makeClip(dir, "b.mp4", "darkred"),
      makeClip(dir, "c.mp4", "seagreen"),
    ];
    const id = await shotId(request, projectId, sceneId);
    for (let index = 0; index < clips.length; index += 1) {
      const assetId = await upload(request, projectId, clips[index], `ticker-${index}`);
      await importVideo(request, projectId, sceneId, id, assetId);
    }

    await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${sceneId}`);
    await expect(page.getByTestId("film-timeline-track")).toBeVisible({ timeout: 45_000 });
    const ticker = page.getByTestId("film-timeline-track-ticker");
    await expect(ticker).toBeEnabled();
    await expect(page.getByTestId("film-timeline-transport").locator("button")).toHaveCount(7);
    await expect(page.getByTestId("film-timeline-skip-back").locator("svg")).toBeVisible();
    await expect(page.getByTestId("film-timeline-skip-forward").locator("svg")).toBeVisible();

    const overflow = await ticker.evaluate((el) => Number((el as HTMLInputElement).max));
    expect(overflow).toBeGreaterThan(40);
    await ticker.evaluate((el) => {
      const input = el as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(input, String(Math.round(Number(input.max) * 0.65)));
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await expect.poll(() => scrollLeft(page)).toBeGreaterThan(40);

    const scrolled = await scrollLeft(page);
    await ticker.evaluate((el) => {
      const input = el as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(input, "0");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await expect.poll(() => scrollLeft(page)).toBeLessThan(scrolled);

    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await page.getByRole("button", { name: "Beginning of Scene" }).click();
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 1");
    await page.getByTestId("film-timeline-skip-forward").click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(5, 0);
    await page.getByTestId("film-timeline-skip-back").click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(0, 0);
    await page.getByRole("button", { name: "End of Batch" }).click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(20, 0);
    await page.getByTestId("film-timeline-skip-forward").click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(25, 0);
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 2");

    await page.getByRole("button", { name: "Start of Batch" }).click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(20, 0);
    await page.getByRole("button", { name: "Beginning of Scene" }).click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(0, 0);
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 1");
    await page.getByRole("button", { name: "End of Scene" }).click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(60, 0);
    await page.getByTestId("film-timeline-skip-forward").click();
    await expect.poll(() => sceneTime(page)).toBeCloseTo(60, 0);

    await page.getByRole("button", { name: "Beginning of Scene" }).click();
    await page.getByTestId("preview-video-retake").click();
    await page.getByTestId("film-timeline-skip-forward").click();
    await page.getByTestId("timeline-retake-mark-in").click();
    await page.getByTestId("film-timeline-skip-forward").click();
    await page.getByTestId("timeline-retake-mark-out").click();
    await expect(page.getByTestId("film-timeline-mark-in")).toBeVisible();
    await expect(page.getByTestId("film-timeline-mark-out")).toBeVisible();

    await expect(page.getByTestId("preview-video-fullscreen")).toBeEnabled();
    await page.getByTestId("preview-video-fullscreen").click();
    await expect(page.getByTestId("preview-fs-rewind-5").locator("svg")).toBeVisible();
    await expect(page.getByTestId("preview-fs-forward-5").locator("svg")).toBeVisible();
    await expect(page.getByTestId("preview-fs-rewind-5")).not.toHaveText(/-5s/);
    await page.getByTestId("preview-fs-exit").click();

    await ticker.evaluate((el) => {
      const input = el as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(input, String(Math.round(Number(input.max) * 0.4)));
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const kept = await scrollLeft(page);
    expect(kept).toBeGreaterThan(20);
    await page.getByTestId("film-timeline-workspace-prompt").click();
    await page.getByTestId("film-timeline-workspace-track").click();
    await expect.poll(() => scrollLeft(page)).toBeGreaterThan(20);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 1" })).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 3" })).toBeVisible();
    await expect(page.getByTestId("film-timeline-track-ticker")).toBeVisible();
    await expect(page.getByTestId("film-timeline-transport").locator("button")).toHaveCount(7);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
