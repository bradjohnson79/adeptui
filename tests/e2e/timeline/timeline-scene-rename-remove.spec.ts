/**
 * Timeline scene card Rename + Remove.
 * Reuses Korri Anadriya. Never POST /api/projects.
 * Never deletes Scene 1, Venture Corridor Dialogue, or Venture Corridor Walk.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const WALK_ID = process.env.ADEPT_SCENE_ID || "b5282a4c-07eb-40db-9d5b-1512eac74dca";
const SCENE1_ID = "1f46b621-46f9-4b7e-8273-202a49e1ca7c";
const DIALOGUE_ID = "ae8e5699-a5d8-4b9b-ad8e-0003d81d3639";
const PROTECTED = new Set([SCENE1_ID, DIALOGUE_ID, WALK_ID]);
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const TEMP_A = "Scene Menu Cert A";
const TEMP_A_RENAMED = "Scene Menu Cert A Renamed";
const TEMP_B = "Scene Menu Cert B";

async function getJson(request: APIRequestContext, path: string) {
  const res = await request.get(`${API}${path}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function postJson(request: APIRequestContext, path: string, body: unknown) {
  const res = await request.post(`${API}${path}`, { data: body });
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function listScenes(request: APIRequestContext) {
  const project = await getJson(request, `/api/projects/${PROJECT_ID}`);
  return (project.scenes || []) as Array<{ id: string; name: string }>;
}

async function cleanupTemps(request: APIRequestContext) {
  const scenes = await listScenes(request);
  for (const scene of scenes) {
    if (PROTECTED.has(scene.id)) continue;
    if (!/^Scene Menu Cert/.test(scene.name) && !/^Scene \d+$/.test(scene.name)) continue;
    if (PROTECTED.has(scene.id)) continue;
    const res = await request.delete(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}`);
    expect([200, 404]).toContain(res.status());
  }
}

async function waitForTimeline(page: Page) {
  await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
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

test.describe("Timeline scene rename + remove", () => {
  test.skip(process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1", "Requires ADEPT_ALLOW_KORRI_MUTATION=1");
  test.setTimeout(180_000);

  test("rename persists, remove is confirmation-gated, leftover temps do not return", async ({
    page,
    request,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await cleanupTemps(request);
    const createdA = await postJson(request, `/api/projects/${PROJECT_ID}/scenes`, {
      name: TEMP_A,
      engine: "minimax-h3",
      duration_sec: 4,
      prompt: "",
    });
    const createdB = await postJson(request, `/api/projects/${PROJECT_ID}/scenes`, {
      name: TEMP_B,
      engine: "minimax-h3",
      duration_sec: 4,
      prompt: "",
    });
    const tempA = createdA.id as string;
    const tempB = createdB.id as string;
    expect(PROTECTED.has(tempA)).toBeFalsy();
    expect(PROTECTED.has(tempB)).toBeFalsy();

    const beforeAssets = await getJson(request, `/api/projects/${PROJECT_ID}`);
    const assetCountBefore = (beforeAssets.assets || []).length;

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/project/${PROJECT_ID}?workspace=timeline&sceneId=${WALK_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await waitForTimeline(page);
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", WALK_ID, {
      timeout: 30_000,
    });
    await openLeftDrawer(page);

    const shell = page.getByTestId("timeline-editor-shell");
    await shell.evaluate((el) => el.setAttribute("data-stability-marker", "keep"));
    await expect(page.getByTestId("timeline-scene-header-title")).toHaveText("Venture Corridor Walk");

    const walkOverflow = page.getByTestId(`scene-overflow-${WALK_ID}`);
    await expect(walkOverflow).toHaveAttribute("aria-label", "Scene options for Venture Corridor Walk");
    await walkOverflow.click();
    await expect(page.getByTestId("scene-menu-rename")).toBeVisible();
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", WALK_ID);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("scene-menu-rename")).toHaveCount(0);

    await page.getByTestId(`scene-overflow-${tempA}`).click();
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", WALK_ID);
    await page.getByTestId("scene-menu-rename").click();
    await expect(page.getByTestId("scene-rename-dialog")).toBeVisible();
    await expect(page.getByTestId("scene-rename-input")).toHaveValue(TEMP_A);
    await page.getByTestId("scene-rename-input").fill(TEMP_A_RENAMED);
    await page.getByTestId("scene-rename-confirm").click();
    await expect(page.getByTestId("scene-rename-dialog")).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByTestId(`scene-block-name-${tempA}`)).toHaveText(TEMP_A_RENAMED);
    await expect(page.getByTestId("timeline-scene-header-title")).toHaveText("Venture Corridor Walk");
    expect(await shell.getAttribute("data-stability-marker")).toBe("keep");

    const persistedRename = await getJson(request, `/api/projects/${PROJECT_ID}/scenes/${tempA}`);
    expect(persistedRename.id).toBe(tempA);
    expect(persistedRename.name).toBe(TEMP_A_RENAMED);

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForTimeline(page);
    await openLeftDrawer(page);
    await expect(page.getByTestId(`scene-block-name-${tempA}`)).toHaveText(TEMP_A_RENAMED);

    await page.getByTestId(`scene-block-${tempA}`).click();
    await expect(page.getByTestId("timeline-scene-header-title")).toHaveText(TEMP_A_RENAMED, { timeout: 20_000 });
    const rightHandle = page.getByTestId("timeline-drawer-right-toggle");
    if ((await rightHandle.getAttribute("aria-expanded")) !== "true") {
      await rightHandle.click();
    }
    await expect(page.getByTestId("timeline-inspector-scene-name")).toHaveValue(TEMP_A_RENAMED);

    await page.getByTestId(`scene-block-${WALK_ID}`).click();
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", WALK_ID, {
      timeout: 20_000,
    });
    await shell.evaluate((el) => el.setAttribute("data-stability-marker", "keep"));

    await page.getByTestId(`scene-overflow-${tempB}`).click();
    await page.getByTestId("scene-menu-remove").click();
    await expect(page.getByTestId("scene-remove-dialog")).toBeVisible();
    await page.getByTestId("scene-remove-cancel").click();
    await expect(page.getByTestId(`scene-block-${tempB}`)).toBeVisible();
    expect(await shell.getAttribute("data-stability-marker")).toBe("keep");
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", WALK_ID);

    await page.getByTestId(`scene-overflow-${tempB}`).click();
    await page.getByTestId("scene-menu-remove").click();
    await page.getByTestId("scene-remove-confirm").click();
    await expect(page.getByTestId(`scene-block-${tempB}`)).toHaveCount(0);
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", WALK_ID);
    expect(await shell.getAttribute("data-stability-marker")).toBe("keep");

    const afterNonActive = await listScenes(request);
    expect(afterNonActive.some((scene) => scene.id === tempB)).toBeFalsy();
    expect(afterNonActive.some((scene) => scene.id === WALK_ID)).toBeTruthy();

    await page.getByTestId(`scene-block-${tempA}`).click();
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", tempA, {
      timeout: 20_000,
    });
    await page.getByTestId(`scene-overflow-${tempA}`).click();
    await page.getByTestId("scene-menu-remove").click();
    await page.getByTestId("scene-remove-confirm").click();
    await expect(page.getByTestId(`scene-block-${tempA}`)).toHaveCount(0);
    await expect(page.getByTestId("timeline-transport")).not.toHaveAttribute("data-scene-id", tempA);
    await expect(page.getByTestId("timeline-transport")).toHaveAttribute("data-scene-id", /.+/, {
      timeout: 20_000,
    });
    const afterActive = await page.getByTestId("timeline-transport").getAttribute("data-scene-id");
    expect(afterActive).toBeTruthy();
    expect(afterActive).not.toBe(tempA);
    expect(afterActive).not.toBe(tempB);

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForTimeline(page);
    await openLeftDrawer(page);
    await expect(page.getByTestId(`scene-block-${tempA}`)).toHaveCount(0);
    await expect(page.getByTestId(`scene-block-${tempB}`)).toHaveCount(0);
    await expect(page.getByTestId(`scene-block-${WALK_ID}`)).toBeVisible();
    await expect(page.getByTestId(`scene-block-${SCENE1_ID}`)).toBeVisible();
    await expect(page.getByTestId(`scene-block-${DIALOGUE_ID}`)).toBeVisible();
    const url = new URL(page.url());
    expect(url.searchParams.get("sceneId")).not.toBe(tempA);
    expect(url.searchParams.get("sceneId")).not.toBe(tempB);

    const afterAssets = await getJson(request, `/api/projects/${PROJECT_ID}`);
    expect((afterAssets.assets || []).length).toBeGreaterThanOrEqual(assetCountBefore);
    const names = (afterAssets.scenes || []).map((scene: { name: string }) => scene.name);
    expect(names).toContain("Scene 1");
    expect(names).toContain("Venture Corridor Dialogue");
    expect(names).toContain("Venture Corridor Walk");
    expect(names).not.toContain(TEMP_A);
    expect(names).not.toContain(TEMP_A_RENAMED);
    expect(names).not.toContain(TEMP_B);

    const leftover = errors.filter(
      (line) =>
        !/favicon|ResizeObserver|fonts\.gstatic|fonts\.googleapis|x-adept-deny-owner-writes|net::ERR|404 \(Not Found\)/i.test(line),
    );
    expect(leftover, leftover.join("\n")).toEqual([]);
  });
});
