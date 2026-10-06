import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Timeline V2 top-action notification (Publish | Update Published | Send to MAGI):
 * the message beneath the bar is event-driven and auto-dismisses after 10s.
 *
 * Live spec (ADEPT_BETA_TARGET=1 → Vite :5173 + Studio API :8758).
 * Disposable project + scenes + ffmpeg-generated Library videos.
 * No publish/MAGI/stitch logic is modified — this only proves the
 * notification surface lifetime behavior.
 */

const UNPUBLISHED_TEXT = "Your scene must be published before it can be sent to MAGI.";
const STALE_TEXT = "Update Published before this scene can be sent to MAGI.";

function makeClip(dir: string, name: string, color: string): Buffer {
  const out = join(dir, name);
  execFileSync(
    "ffmpeg",
    ["-y", "-loglevel", "error", "-f", "lavfi", "-i", `color=c=${color}:duration=2:size=320x180:rate=24`, "-pix_fmt", "yuv420p", out],
    { stdio: "pipe" },
  );
  return readFileSync(out);
}

async function uploadVideo(request: APIRequestContext, projectId: string, file: Buffer, tag: string): Promise<string> {
  const res = await request.post(`/api/projects/${projectId}/assets`, {
    multipart: { file: { name: `${tag}.mp4`, mimeType: "video/mp4", buffer: file }, tag, kind: "video" },
  });
  expect(res.ok(), `upload ${tag} failed: ${res.status()}`).toBeTruthy();
  return String((await res.json()).id || "");
}

async function filmShotId(request: APIRequestContext, projectId: string, sceneId: string): Promise<string> {
  const film = await request.get(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}`);
  expect(film.ok(), `film read failed: ${film.status()}`).toBeTruthy();
  const body = await film.json();
  const existing = (body?.film?.shots || [])[0];
  if (existing?.id) return String(existing.id);
  const created = await request.post(`/api/film-timeline/projects/${projectId}/scenes/${sceneId}/shots`, {
    data: { durationSec: 4, timedPrompt: "" },
  });
  expect(created.ok(), `create shot failed: ${created.status()}`).toBeTruthy();
  const createdBody = await created.json();
  const id = String(createdBody?.shot?.id || createdBody?.film?.shots?.[0]?.id || "");
  expect(id, "shot id after create").toBeTruthy();
  return id;
}

async function importVideo(request: APIRequestContext, projectId: string, sceneId: string, shotId: string, assetId: string) {
  const res = await request.post(
    `/api/film-timeline/projects/${projectId}/scenes/${sceneId}/shots/${shotId}/import-video`,
    { data: { assetId } },
  );
  expect(res.ok(), `import-video failed: ${res.status()} ${await res.text()}`).toBeTruthy();
}

async function openTimeline(page: Page, projectId: string, sceneId: string) {
  // Pin sceneId in the URL so the shell's first film load targets this scene
  // directly. (Without it the shell mounts on the project's auto-created
  // default scene and an immediate re-select races the in-flight mount load —
  // a pre-existing load() stale-resolution race outside this mission's
  // boundary.)
  await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${sceneId}`);
  await expect(page.getByTestId("live-preview-publish-bar")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("film-timeline-scene")).toHaveValue(sceneId, { timeout: 30_000 });
}

test.describe("Timeline top-action 10-second notification", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(120_000);

  let projectId = "";
  let scene1 = "";
  let scene2 = "";
  let videoB = "";

  test.beforeAll(async ({ request }) => {
    const created = await request.post("/api/projects", { data: { name: `Timeline Notice Smoke ${Date.now()}` } });
    expect(created.ok(), `create project failed: ${created.status()}`).toBeTruthy();
    projectId = String((await created.json()).id || "");

    // Unique names: project creation auto-seeds a default "Scene 1".
    for (const name of ["Notice Alpha", "Notice Beta"]) {
      const scene = await request.post(`/api/projects/${projectId}/scenes`, {
        data: { name, engine: "auto", duration_sec: 4, prompt: "" },
      });
      expect(scene.ok(), `create ${name} failed: ${scene.status()}`).toBeTruthy();
      const id = String((await scene.json()).id || "");
      if (name === "Notice Alpha") scene1 = id;
      else scene2 = id;
    }

    const dir = mkdtempSync(join(tmpdir(), "adept-notice-"));
    try {
      const clipA = makeClip(dir, "clip-a.mp4", "steelblue");
      const clipB = makeClip(dir, "clip-b.mp4", "darkred");
      const videoA = await uploadVideo(request, projectId, clipA, "notice-clip-a");
      videoB = await uploadVideo(request, projectId, clipB, "notice-clip-b");

      // Scene 1: two segments + stitch → stitch-ready, unpublished.
      const shot1 = await filmShotId(request, projectId, scene1);
      await importVideo(request, projectId, scene1, shot1, videoA);
      await importVideo(request, projectId, scene1, shot1, videoA);
      const stitch = await request.post(
        `/api/film-timeline/projects/${projectId}/scenes/${scene1}/shots/${shot1}/stitch`,
      );
      expect(stitch.ok(), `stitch failed: ${stitch.status()} ${await stitch.text()}`).toBeTruthy();
      const stitched = await stitch.json();
      expect(String(stitched?.film?.shots?.[0]?.state?.stitchStatus || "")).toBe("ready");
      expect(String(stitched?.film?.shots?.[0]?.state?.stitchAssetId || "")).toBeTruthy();

      // Scene 2: one segment → preview actions available, unpublished.
      const shot2 = await filmShotId(request, projectId, scene2);
      await importVideo(request, projectId, scene2, shot2, videoA);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  test("appears on trigger, lives 10s, retrigger resets, buttons unchanged, no ghost", async ({ page }) => {
    await openTimeline(page, projectId, scene1);

    const note = page.getByTestId("film-timeline-magi-note");
    const publishBtn = page.getByTestId("live-preview-publish");
    const updateBtn = page.getByTestId("live-preview-update-published");
    const magiBtn = page.getByTestId("film-timeline-send-magi");

    // Not pinned: no message before any trigger.
    await expect(note).toHaveCount(0);
    await expect(publishBtn).toBeVisible();
    await expect(updateBtn).toBeVisible();
    await expect(magiBtn).toBeVisible();
    await expect(magiBtn).toBeEnabled();

    // 1+2. Trigger Send to MAGI while unpublished → message appears immediately.
    await magiBtn.click();
    await expect(note).toHaveCount(1);
    await expect(note).toHaveText(UNPUBLISHED_TEXT);

    // 3. Still readable mid-lifetime.
    await page.waitForTimeout(7000);
    await expect(note).toHaveText(UNPUBLISHED_TEXT);

    // 6. Trigger again → the 10-second timer restarts.
    await magiBtn.click();
    await page.waitForTimeout(7000); // 14s since the first trigger: original timer would have expired.
    await expect(note).toHaveText(UNPUBLISHED_TEXT);

    // 4. Gone automatically at ~10s after the second trigger.
    await expect(note).toHaveCount(0, { timeout: 7000 });

    // 5. Top buttons unchanged after expiry; no stale text left in the bar.
    await expect(publishBtn).toBeVisible();
    await expect(updateBtn).toBeVisible();
    await expect(magiBtn).toBeVisible();
    await expect(page.getByTestId("live-preview-publish-bar")).not.toContainText(UNPUBLISHED_TEXT);

    // 9. No delayed ghost message after expiry.
    await page.waitForTimeout(1500);
    await expect(note).toHaveCount(0);
  });

  test("scene switch clears the stale notification", async ({ page }) => {
    await openTimeline(page, projectId, scene1);

    const note = page.getByTestId("film-timeline-magi-note");
    await page.getByTestId("film-timeline-send-magi").click();
    await expect(note).toHaveText(UNPUBLISHED_TEXT);

    // 8. Switching scenes clears the message immediately — it cannot linger
    // over Scene 2.
    await page.getByTestId("film-timeline-scene").selectOption(scene2);
    await expect(note).toHaveCount(0);

    // Back on Scene 1 the expired message is not resurrected…
    await page.getByTestId("film-timeline-scene").selectOption(scene1);
    await expect(note).toHaveCount(0);

    // …but a fresh trigger works again for another full lifetime.
    await page.getByTestId("film-timeline-send-magi").click();
    await expect(note).toHaveText(UNPUBLISHED_TEXT);
    await expect(note).toHaveCount(0, { timeout: 12_000 });
  });

  test("a different notification replaces the previous one with its own 10s lifetime", async ({ page }) => {
    await openTimeline(page, projectId, scene1);

    const note = page.getByTestId("film-timeline-magi-note");
    const publishBtn = page.getByTestId("live-preview-publish");
    const updateBtn = page.getByTestId("live-preview-update-published");
    const magiBtn = page.getByTestId("film-timeline-send-magi");

    // Note A: publish-required warning.
    await magiBtn.click();
    await expect(note).toHaveText(UNPUBLISHED_TEXT);

    // Publish through the real button (logic untouched — presentation-only mission).
    await publishBtn.click();
    await expect(publishBtn).toBeDisabled({ timeout: 30_000 }); // gate left "unpublished"

    // Make the stitch stale through the real creator path: add another video
    // from the Project Library (import marks the stitch stale server-side).
    await page.getByTestId("film-timeline-workspace-track").click();
    await page.getByTestId("film-timeline-add-from-library").click();
    const modal = page.getByTestId("timeline-add-from-project-library");
    await expect(modal).toBeVisible({ timeout: 30_000 });
    await modal.getByTestId(`library-card-${videoB}`).click();
    await modal.getByTestId("timeline-add-from-project-library-add").click();
    await expect(updateBtn).toBeEnabled({ timeout: 30_000 }); // gate now "stale"

    // 7. Note B replaces Note A and gets its own 10-second lifetime.
    await magiBtn.click();
    await expect(note).toHaveText(STALE_TEXT);
    await page.waitForTimeout(7000);
    await expect(note).toHaveText(STALE_TEXT);
    await expect(note).toHaveCount(0, { timeout: 7000 });
  });
});
