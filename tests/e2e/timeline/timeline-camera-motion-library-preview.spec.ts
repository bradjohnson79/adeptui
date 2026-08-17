/**
 * Camera motion references + Library Quick Preview.
 * Schnick Coffee only. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

type BindingRow = {
  id: string;
  alias?: string;
  asset_id?: string;
  identity_id?: string;
  media_kind?: string;
  reference_type?: string;
};

type CameraClip = {
  id: string;
  text?: string;
  reference_binding_ids?: string[];
};

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 10_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

async function firstScene(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const scenes = body.scenes || body.items || body || [];
  const scene = Array.isArray(scenes) ? scenes[0] : null;
  expect(scene?.id).toBeTruthy();
  return scene as { id: string };
}

async function getDirector(request: APIRequestContext, sceneId: string) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}/director`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function putDirector(request: APIRequestContext, sceneId: string, director: unknown) {
  const res = await request.put(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}/director`, {
    data: director,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function listedBindings(request: APIRequestContext) {
  const listed = await request.get(
    `${API}/api/projects/${PROJECT_ID}/references?scope_type=project&scope_id=${PROJECT_ID}`,
  );
  expect(listed.ok()).toBeTruthy();
  return ((await listed.json()).items || []) as BindingRow[];
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

async function clickDrawer(page: Page, side: "left" | "right") {
  const handle = page.getByTestId(`timeline-drawer-${side}-toggle`);
  const box = await handle.boundingBox();
  expect(box).toBeTruthy();
  await handle.click({ position: { x: Math.max(2, box!.width / 2), y: 16 } });
}

async function openDrawer(page: Page, side: "left" | "right") {
  if ((await page.getByTestId(`timeline-drawer-${side}-toggle`).getAttribute("aria-expanded")) !== "true") {
    await clickDrawer(page, side);
  }
  await expect(page.getByTestId(`timeline-drawer-${side}-toggle`)).toHaveAttribute("aria-expanded", "true");
  await expect
    .poll(async () => {
      const box = await page.getByTestId(`timeline-splitter-${side}`).boundingBox();
      if (!box) return 0;
      return side === "left" ? box.x : page.viewportSize()!.width - box.x;
    })
    .toBeGreaterThan(200);
  await page.waitForTimeout(240);
}

async function ensureVideoBinding(request: APIRequestContext, existing: BindingRow[]) {
  const found = existing.find((item) => item.media_kind === "video");
  if (found) return { binding: found, created: false };
  const projectRes = await request.get(`${API}/api/projects/${PROJECT_ID}`);
  expect(projectRes.ok(), await projectRes.text()).toBeTruthy();
  const assets = ((await projectRes.json()).assets || []) as Array<{ id: string; kind?: string; tag?: string }>;
  const video = assets.find((item) => item.kind === "video" && (item.tag || "").toLowerCase().includes("korripose"))
    || assets.find((item) => item.kind === "video");
  expect(video?.id, "Schnick Library needs a video for Camera motion reference").toBeTruthy();
  const created = await request.post(`${API}/api/projects/${PROJECT_ID}/references`, {
    data: {
      asset_id: video!.id,
      scope_type: "project",
      scope_id: PROJECT_ID,
      reference_type: "video",
      media_kind: "video",
      alias: video!.tag || "KorriPoseVideo",
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const body = (await created.json()) as BindingRow;
  const listed = await listedBindings(request);
  const resolved = listed.find((item) => item.id === body.id) || listed.find((item) => item.asset_id === video!.id) || body;
  return { binding: resolved, created: true };
}

test.describe("Timeline camera motion + Library Quick Preview", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("Camera @ and * store canonical IDs, rename keeps the video, unsupported stays honest", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    const original = await getDirector(request, scene.id);
    const bindings = await listedBindings(request);
    const korri =
      bindings.find((item) => (item.alias || "").toLowerCase() === "korri" && (item.media_kind === "entity" || item.reference_type === "character")) ||
      bindings.find((item) => item.media_kind === "entity" && item.reference_type === "character");
    expect(korri?.id, "Schnick needs a Character reference such as @Korri").toBeTruthy();
    const videoAttach = await ensureVideoBinding(request, bindings);
    const video = videoAttach.binding;
    const originalAlias = video.alias || "KorriPoseVideo";

    try {
      await openTimeline(page, scene.id);
      await page.getByTestId("timeline-reset-layout").click();
      await page.waitForTimeout(240);
      await openDrawer(page, "right");
      await expect(page.getByTestId("timeline-image-reference-track")).toHaveCount(0);
      await expect(page.getByTestId("timeline-video-reference-track")).toHaveCount(0);

      await page.getByTestId("track-add-camera").click();
      const cameraClip = page.locator('[data-testid^="track-clip-camera-"]').last();
      await expect(cameraClip).toBeVisible({ timeout: 20_000 });
      await cameraClip.click();
      const input = page.getByTestId("ref-token-input-camera");
      await expect(input).toBeVisible({ timeout: 20_000 });
      await input.fill(`@${korri!.alias || "Korri"}`);
      const korriRow = page.getByTestId(`ref-token-row-${korri!.id}`);
      await expect(korriRow).toBeVisible();
      await expect(korriRow).toContainText("Character");
      await korriRow.click();

      await expect
        .poll(async () => {
          const tl = await getDirector(request, scene.id);
          return (tl.camera_clips || []).some((clip: CameraClip) => (clip.reference_binding_ids || []).includes(korri!.id));
        }, { timeout: 20_000 })
        .toBeTruthy();
      await page.waitForTimeout(400);

      await input.fill(`*${video.alias || "Korri"}`);
      const videoRow = page.getByTestId(`ref-token-row-${video.id}`);
      await expect(videoRow).toBeVisible();
      await expect(videoRow).toContainText("Video");
      await videoRow.click();

      let saved: CameraClip | undefined;
      await expect
        .poll(async () => {
          const tl = await getDirector(request, scene.id);
          saved = (tl.camera_clips || []).find((clip: CameraClip) =>
            (clip.reference_binding_ids || []).includes(korri!.id) &&
            (clip.reference_binding_ids || []).includes(video.id),
          );
          return Boolean(saved?.id);
        }, { timeout: 20_000 })
        .toBeTruthy();
      expect(saved!.reference_binding_ids).toContain(korri!.id);
      expect(saved!.reference_binding_ids).toContain(video.id);

      const preflight = await request.get(
        `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${scene.id}/preflight`,
      );
      expect(preflight.ok(), await preflight.text()).toBeTruthy();
      const findings = ((await preflight.json()).findings || []) as Array<{ code?: string; message?: string }>;
      const unsupported = findings.filter((item) =>
        ["VIDEO_MOTION_REFERENCE_UNSUPPORTED", "VIDEO_REFERENCE_UNSUPPORTED"].includes(String(item.code || "")),
      );
      await expect(page.getByTestId("camera-ref-counts")).toContainText(/Video refs/i);
      await expect(page.getByTestId("camera-ref-capability-warning")).toBeVisible();
      await expect(page.getByTestId("camera-ref-capability-warning")).toContainText(
        "does not support video motion references",
      );
      expect(unsupported.length, "MiniMax must refuse video motion references honestly").toBeGreaterThan(0);
      const afterWarn = await getDirector(request, scene.id);
      const still = (afterWarn.camera_clips || []).find((clip: CameraClip) => clip.id === saved!.id);
      expect(still?.reference_binding_ids).toContain(video.id);
      expect(still?.reference_binding_ids).toContain(korri!.id);

      const rename = await request.patch(`${API}/api/projects/${PROJECT_ID}/references/${video.id}`, {
        data: { alias: "KorriDanceMotion" },
      });
      expect(rename.ok(), await rename.text()).toBeTruthy();
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId(`camera-token-summary-${saved!.id}`)).toContainText("KorriDanceMotion");
      const renamedDirector = await getDirector(request, scene.id);
      const renamedClip = (renamedDirector.camera_clips || []).find((clip: CameraClip) => clip.id === saved!.id);
      expect(renamedClip?.reference_binding_ids).toContain(video.id);
      expect(renamedClip?.reference_binding_ids).toContain(korri!.id);
      const renamedBinding = (await listedBindings(request)).find((item) => item.id === video.id);
      expect(renamedBinding?.asset_id).toBe(video.asset_id);
    } finally {
      await request.patch(`${API}/api/projects/${PROJECT_ID}/references/${video.id}`, {
        data: { alias: originalAlias },
      });
      if (videoAttach.created) {
        await request.delete(`${API}/api/projects/${PROJECT_ID}/references/${video.id}`);
      }
      await putDirector(request, scene.id, original);
    }
  });

  test("Library double-click opens read-only Quick Preview for image, video, and audio", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    const original = await getDirector(request, scene.id);
    const projectRes = await request.get(`${API}/api/projects/${PROJECT_ID}`);
    expect(projectRes.ok(), await projectRes.text()).toBeTruthy();
    const assets = ((await projectRes.json()).assets || []) as Array<{
      id: string;
      kind?: string;
      tag?: string;
      filename?: string;
    }>;
    const image = assets.find((item) => item.kind === "image");
    const video = assets.find((item) => item.kind === "video");
    const audio = assets.find((item) => item.kind === "audio");
    expect(image?.id, "Schnick Library needs an image").toBeTruthy();
    expect(video?.id, "Schnick Library needs a video").toBeTruthy();
    expect(audio?.id, "Schnick Library needs audio").toBeTruthy();

    try {
      await openTimeline(page, scene.id);
      await page.getByTestId("timeline-reset-layout").click();
      await page.waitForTimeout(240);
      await openDrawer(page, "left");
      const search = page.getByTestId("asset-library-search");
      await expect(search).toBeVisible();

      const reveal = async (asset: { id: string; tag?: string; filename?: string }) => {
        await search.fill(asset.tag || asset.filename || asset.id);
        const card = page.getByTestId(`asset-library-item-${asset.id}`);
        await expect(card).toBeAttached();
        return card;
      };
      const fire = async (card: Locator, type: "click" | "dblclick") => {
        await card.evaluate((el, eventType) => {
          el.dispatchEvent(new MouseEvent(eventType, { bubbles: true, cancelable: true, view: window }));
        }, type);
      };

      const imageCard = await reveal(image!);
      await fire(imageCard, "click");
      await expect(page.getByTestId("library-quick-preview")).toHaveCount(0);
      await fire(imageCard, "dblclick");
      await expect(page.getByTestId("library-quick-preview")).toBeVisible();
      await expect(page.getByTestId("library-quick-preview-image")).toBeVisible();
      await page.getByTestId("library-quick-preview-close").click();
      await expect(page.getByTestId("library-quick-preview")).toHaveCount(0);

      const videoCard = await reveal(video!);
      await fire(videoCard, "dblclick");
      await expect(page.getByTestId("library-quick-preview-video")).toBeVisible();
      await expect(page.locator('[data-testid="library-quick-preview-video"] video')).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("library-quick-preview")).toHaveCount(0);

      const audioCard = await reveal(audio!);
      await fire(audioCard, "dblclick");
      await expect(page.getByTestId("library-quick-preview-audio")).toBeVisible();
      await expect(page.locator('[data-testid="library-quick-preview-audio"] audio')).toBeVisible();
      await page.getByTestId("library-quick-preview-close").click();
      await expect(page.getByTestId("library-quick-preview")).toHaveCount(0);

      const imageAgain = await reveal(image!);
      await imageAgain.getByTestId(`asset-add-timeline-${image!.id}`).evaluate((el) => {
        el.dispatchEvent(new MouseEvent("dblclick", { bubbles: true, cancelable: true, view: window }));
      });
      await expect(page.getByTestId("library-quick-preview")).toHaveCount(0);

      const after = await getDirector(request, scene.id);
      expect(JSON.stringify(after.camera_clips || [])).toBe(JSON.stringify(original.camera_clips || []));
      expect((after.prompt_segments || []).length).toBe((original.prompt_segments || []).length);
    } finally {
      await putDirector(request, scene.id, original);
    }
  });
});
