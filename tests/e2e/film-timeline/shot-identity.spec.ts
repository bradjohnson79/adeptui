import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/** Live Timeline V2 shot identity. Library import stands in for the first picture so the test does not start a GPU render. */

function makeClip(dir: string): Buffer {
  const out = join(dir, "clip.mp4");
  execFileSync(
    "ffmpeg",
    ["-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=steelblue:duration=2:size=320x180:rate=24", "-pix_fmt", "yuv420p", out],
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
    data: { durationSec: 4, timedPrompt: "" },
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

test("shot numbers stay stable across prompt, prepend, delete, and reload", async ({ page, request }) => {
  test.setTimeout(120_000);
  const created = await request.post("/api/projects", { data: { name: `Shot Identity ${Date.now()}` } });
  expect(created.ok()).toBeTruthy();
  const projectId = String((await created.json()).id || "");
  const scene = await request.post(`/api/projects/${projectId}/scenes`, {
    data: { name: "Identity Scene", engine: "auto", duration_sec: 4, prompt: "" },
  });
  expect(scene.ok()).toBeTruthy();
  const sceneId = String((await scene.json()).id || "");

  await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${sceneId}`);
  await expect(page.getByTestId("film-timeline-shot-tag")).toHaveText("#Shot1", { timeout: 45_000 });

  const dir = mkdtempSync(join(tmpdir(), "adept-shot-"));
  try {
    const file = makeClip(dir);
    const assets = [];
    for (const tag of ["id-a", "id-b", "id-c", "id-d"]) assets.push(await upload(request, projectId, file, tag));
    const id = await shotId(request, projectId, sceneId);
    await importVideo(request, projectId, sceneId, id, assets[0]);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 1" })).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("film-timeline-preview-shot")).toHaveText("Shot 1");

    await page.getByTestId("film-timeline-add-batch").click();
    await expect(page.getByTestId("film-timeline-shot-tag")).toHaveText("#Shot2");
    await expect(page.getByTestId("film-timeline-continue")).toBeVisible();

    await page.getByTestId("film-timeline-workspace-track").click();
    await page.getByTestId("film-timeline-add-previous").click();
    await expect(page.getByTestId("film-timeline-shot-tag")).toHaveText("#Shot2");
    await expect(page.getByTestId("film-timeline-prepend")).toBeVisible();

    await importVideo(request, projectId, sceneId, id, assets[1]);
    await importVideo(request, projectId, sceneId, id, assets[2]);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 2" })).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 3" })).toBeVisible();

    const shot2 = page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 2" });
    await shot2.getByTestId("film-timeline-delete-video").click();
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 2" })).toHaveCount(0);
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 3" })).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 1" })).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 3" })).toBeVisible();
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 2" })).toHaveCount(0);

    await importVideo(request, projectId, sceneId, id, assets[3]);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 4" })).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("film-timeline-batch").filter({ hasText: "Shot 3" })).toBeVisible();
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
