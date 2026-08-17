/**
 * Timeline layout + Library references. Schnick Coffee only.
 * Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

type BindingRow = {
  id: string;
  alias?: string;
  asset_id: string;
  media_kind?: string;
  display_token?: string;
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
  return scene as { id: string; name?: string };
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

test.describe("Timeline layout + library references", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("resizable panes, one fullscreen, library-only, typed references, alias rename persistence", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    const projectRes = await request.get(`${API}/api/projects/${PROJECT_ID}`);
    expect(projectRes.ok(), await projectRes.text()).toBeTruthy();
    const project = await projectRes.json();
    const assets = project.assets || [];
    const videos = (Array.isArray(assets) ? assets : []).filter((a: { kind?: string }) => a.kind === "video");
    const images = (Array.isArray(assets) ? assets : []).filter((a: { kind?: string }) => a.kind === "image");
    expect(videos.length, "Schnick Library needs a video for the alias-rename persistence gate").toBeGreaterThan(0);
    expect(images.length, "Schnick Library needs an image for wrong-type reject").toBeGreaterThan(0);

    await openTimeline(page, scene.id);
    await expect(page.getByTestId("timeline-splitter-left")).toBeVisible();
    await expect(page.getByTestId("timeline-splitter-right")).toBeVisible();
    await expect(page.getByTestId("timeline-reset-layout")).toBeVisible();
    await expect(page.getByTestId("timeline-viewer-fit")).toBeVisible();
    await expect(page.getByTestId("timeline-viewer-preset")).toBeVisible();
    await expect(page.getByTestId("timeline-viewer-aspect")).toBeVisible();
    await expect(page.getByTestId("timeline-viewer-pause")).toBeVisible();
    await expect(page.getByTestId("workspace-fullscreen-controls")).toBeVisible();
    await expect(page.getByTestId("timeline-viewer-fullscreen")).toHaveCount(0);
    await expect(page.getByText("Upload image", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Upload video", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Upload audio", { exact: true })).toHaveCount(0);
    await expect(page.getByTestId("timeline-image-reference-track")).toHaveCount(0);
    await expect(page.getByTestId("timeline-video-reference-track")).toHaveCount(0);

    const layout = page.getByTestId("timeline-editor-shell").locator(".timeline-v2__body");
    const before = await layout.evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    const left = page.getByTestId("timeline-splitter-left");
    const box = await left.boundingBox();
    expect(box).toBeTruthy();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + 40);
    await page.mouse.down();
    await page.mouse.move(box!.x + 80, box!.y + 40);
    await page.mouse.up();
    const afterDrag = await layout.evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(afterDrag).not.toEqual(before);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    const afterReload = await page
      .getByTestId("timeline-editor-shell")
      .locator(".timeline-v2__body")
      .evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(afterReload).toEqual(afterDrag);

    await page.getByTestId("timeline-reset-layout").click();
    await expect
      .poll(async () =>
        page
          .getByTestId("timeline-editor-shell")
          .locator(".timeline-v2__body")
          .evaluate((el) => getComputedStyle(el).gridTemplateColumns),
      )
      .not.toEqual(afterDrag);

    const video = (videos.find((a: { tag?: string }) => a.tag === "KorriPoseVideo") || videos[0]) as {
      id: string;
      tag?: string;
      filename?: string;
    };
    const image = images[0] as { id: string; tag?: string; filename?: string };

    const listedBindings = async () => {
      const listed = await request.get(
        `${API}/api/projects/${PROJECT_ID}/references?scope_type=project&scope_id=${PROJECT_ID}`,
      );
      expect(listed.ok()).toBeTruthy();
      return ((await listed.json()).items || []) as BindingRow[];
    };

    const search = page.getByTestId("asset-library-search");
    await search.fill(video.tag || video.filename || video.id);
    const addRef = page.getByTestId(`asset-add-reference-${video.id}`);
    await expect(addRef).toBeVisible({ timeout: 20_000 });
    await addRef.evaluate((el: HTMLElement) => el.click());

    let binding: BindingRow | undefined;
    await expect
      .poll(async () => {
        binding = (await listedBindings()).find((item) => item.asset_id === video.id);
        return Boolean(binding?.id);
      }, { timeout: 20_000 })
      .toBeTruthy();
    expect(binding?.media_kind).toBe("video");
    await expect(page.getByTestId(`reference-chip-${binding!.id}`)).toBeVisible({ timeout: 20_000 });

    await search.fill(image.tag || image.filename || image.id);
    await page.getByTestId(`asset-add-reference-${image.id}`).click();
    let imageBinding: BindingRow | undefined;
    await expect
      .poll(async () => {
        imageBinding = (await listedBindings()).find((item) => item.asset_id === image.id);
        return Boolean(imageBinding?.id);
      }, { timeout: 20_000 })
      .toBeTruthy();

    await page.getByTestId("timeline-toolbar-prompt-add").click();
    const promptClip = page.locator('[data-testid^="track-clip-prompt-"]').last();
    await expect(promptClip).toBeVisible({ timeout: 20_000 });
    await promptClip.click();
    const input = page.getByTestId("ref-token-input-prompt");
    await expect(input).toBeVisible({ timeout: 20_000 });
    await input.fill(`*${binding!.alias || "Kor"}`);
    const row = page.getByTestId(`ref-token-row-${binding!.id}`);
    await expect(row).toBeVisible();
    await expect(row).toContainText("Video");
    await row.click();

    await expect
      .poll(async () => {
        const beforeDirector = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`);
        const beforeTl = await beforeDirector.json();
        const seg = (beforeTl.prompt_segments || []).find((item: { reference_binding_ids?: string[] }) =>
          (item.reference_binding_ids || []).includes(binding!.id),
        );
        return Boolean(seg);
      }, { timeout: 20_000 })
      .toBeTruthy();

    await input.fill(`#${(image.tag || "Schn").slice(0, 4)}`);
    const imageRow = page.getByTestId(`ref-token-row-${imageBinding!.id}`);
    await expect(imageRow).toBeVisible();
    await imageRow.click();
    await expect
      .poll(async () => {
        const director = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`);
        const tl = await director.json();
        const seg = (tl.prompt_segments || []).find((item: { reference_binding_ids?: string[] }) =>
          (item.reference_binding_ids || []).includes(binding!.id),
        );
        return Boolean(seg?.reference_binding_ids?.includes(imageBinding!.id));
      }, { timeout: 20_000 })
      .toBeTruthy();

    await page.getByTestId(`reference-chip-${binding!.id}`).click();
    await page.getByTestId(`reference-alias-input-${binding!.id}`).fill("KorriDanceMotion");
    await page.getByTestId(`reference-alias-save-${binding!.id}`).click();
    await expect(page.getByTestId(`reference-chip-${binding!.id}`)).toContainText("KorriDanceMotion");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId(`reference-chip-${binding!.id}`)).toContainText("KorriDanceMotion");
    const afterDirector = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`);
    const afterTl = await afterDirector.json();
    const afterSeg = (afterTl.prompt_segments || []).find((item: { reference_binding_ids?: string[] }) =>
      (item.reference_binding_ids || []).includes(binding!.id),
    );
    expect(afterSeg?.reference_binding_ids, "prompt must key off binding id, not alias text").toContain(binding!.id);
    await expect(page.getByTestId(`prompt-token-summary-${afterSeg.id}`)).toContainText("KorriDanceMotion");

    const renamed = (await listedBindings()).find((item) => item.id === binding!.id);
    expect(renamed?.alias).toBe("KorriDanceMotion");
    expect(renamed?.asset_id).toBe(binding!.asset_id);

    await page.getByTestId(`reference-remove-${binding!.id}`).click();
    await expect(page.getByTestId(`reference-chip-${binding!.id}`)).toHaveCount(0);
    const stillProject = await request.get(`${API}/api/projects/${PROJECT_ID}`);
    expect(stillProject.ok(), await stillProject.text()).toBeTruthy();
    const stillAssets = (await stillProject.json()).assets || [];
    expect(
      (Array.isArray(stillAssets) ? stillAssets : []).some((item: { id?: string }) => item.id === video.id),
      "removing a Timeline reference must not delete the Library video",
    ).toBeTruthy();
  });
});
