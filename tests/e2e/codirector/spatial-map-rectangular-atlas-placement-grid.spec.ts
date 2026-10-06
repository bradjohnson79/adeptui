/**
 * Rectangular Atlas + canonical circle-in-square placement grid + entity placement.
 * Reuses the Korri Anadriya project. Never POST /api/projects. Never Reset Map on Venture.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const KORRI_ID = "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed";
const ATLAS_16X9 = "7a70d734-69d7-4b83-ac1e-61850aa36bb8";
const MAP_16X9 = "Native Aspect 16:9";
const MAP_VENTURE = /venture corridor walk/i;
const PROBE_PROP_NAME = "Corridor Lantern";

test.setTimeout(8 * 60 * 1000);

type Placed = {
  id?: string;
  normalizedX?: number | null;
  normalizedY?: number | null;
  characterId?: string;
  propId?: string | null;
  cameraSlot?: number;
  label?: string;
  tag?: string;
};

type MapDoc = {
  id: string;
  title?: string;
  backgroundAssetId?: string | null;
  backgroundAlignment?: {
    offsetX?: number;
    offsetY?: number;
    scale?: number;
    sourceWidth?: number;
    sourceHeight?: number;
    sourceAspectRatio?: number;
  };
  characters?: Placed[];
  props?: Placed[];
  cameras?: Placed[];
};

async function listMaps(request: APIRequestContext): Promise<MapDoc[]> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), "list Spatial Maps").toBeTruthy();
  return ((await res.json()).documents || []) as MapDoc[];
}

async function mapByTitle(request: APIRequestContext, title: string | RegExp): Promise<MapDoc> {
  const found = (await listMaps(request)).find((m) =>
    typeof title === "string" ? m.title === title : title.test(String(m.title || "")),
  );
  expect(found, `map ${String(title)}`).toBeTruthy();
  return found!;
}

async function getMap(request: APIRequestContext, mapId: string): Promise<MapDoc> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
  expect(res.ok(), `GET map ${mapId}`).toBeTruthy();
  return ((await res.json()).document || {}) as MapDoc;
}

async function openMap(page: Page, mapId: string, title?: string) {
  const alreadySpatial = /[?&]workspace=spatial(?:&|$)/.test(page.url());
  if (!alreadySpatial) {
    await page.goto(`/project/${PROJECT_ID}?workspace=spatial`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
  }
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
  const select = page.locator("#spatial-map-select");
  await expect(select).toBeVisible({ timeout: 15_000 });
  await select.selectOption(mapId);
  await expect(select).toHaveValue(mapId, { timeout: 15_000 });
  if (title) {
    await expect(page.getByRole("heading", { name: title })).toBeVisible({ timeout: 15_000 });
  }
  await expect(page.getByTestId("spatial-map-grid")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("spatial-map-atlas-layer")).toBeVisible({ timeout: 20_000 });
}

async function ensureWidePlate(request: APIRequestContext, mapId: string) {
  const current = await getMap(request, mapId);
  if (current.backgroundAssetId === ATLAS_16X9 && Number(current.backgroundAlignment?.sourceWidth) === 1280) {
    return;
  }
  const res = await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`, {
    data: {
      backgroundAssetId: ATLAS_16X9,
      backgroundAlignment: {
        offsetX: 0,
        offsetY: 0,
        scale: 1,
        sourceWidth: 1280,
        sourceHeight: 720,
        sourceAspectRatio: 16 / 9,
      },
    },
  });
  expect(res.ok(), `restore 16:9 atlas: ${await res.text()}`).toBeTruthy();
}

async function ensureProbeProp(request: APIRequestContext): Promise<{ id: string; created: boolean }> {
  const listed = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/props`);
  expect(listed.ok(), "list Korri props").toBeTruthy();
  const items = (((await listed.json()) as { items?: Array<{ id: string; name?: string }> }).items || []);
  const existing = items.find((item) => item.name === PROBE_PROP_NAME) || items[0];
  if (existing?.id) return { id: existing.id, created: false };
  const created = await request.post(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/props`, {
    data: { name: PROBE_PROP_NAME },
  });
  expect(created.ok(), `create Korri prop: ${await created.text()}`).toBeTruthy();
  const body = (await created.json()) as { id?: string };
  expect(body.id, "created prop id").toBeTruthy();
  return { id: body.id!, created: true };
}

async function clearSandboxEntities(request: APIRequestContext, mapId: string) {
  const doc = await getMap(request, mapId);
  for (const item of doc.characters || []) {
    if (!item.id) continue;
    await request.delete(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/characters/${item.id}`);
  }
  for (const item of doc.props || []) {
    if (!item.id) continue;
    await request.delete(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/props/${item.id}`);
  }
  for (const item of doc.cameras || []) {
    if (!item.id) continue;
    await request.delete(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/cameras/${item.id}`);
  }
}

async function clickGridAt(page: Page, nx: number, ny: number) {
  const grid = page.getByTestId("spatial-map-grid");
  await grid.scrollIntoViewIfNeeded();
  const box = await grid.boundingBox();
  expect(box, "spatial map grid box").toBeTruthy();
  await grid.click({
    position: { x: box!.width * nx, y: box!.height * ny },
    force: true,
  });
}

async function setWorkspaceZoom(page: Page, value: number) {
  await page.getByTestId("map-zoom-slider").evaluate((el, next) => {
    const input = el as HTMLInputElement;
    const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
    desc?.set?.call(input, String(next));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
  await expect(page.getByTestId("spatial-map-viewport")).toHaveAttribute("data-zoom", String(value));
}

async function measureFill(page: Page) {
  return page.evaluate(() => {
    const frame = document.querySelector("[data-testid='spatial-map-viewport-frame']") as HTMLElement | null;
    const image = document.querySelector("[data-testid='spatial-map-atlas-layer'] image") as SVGGraphicsElement | null;
    if (!frame || !image) return { frameW: 0, frameH: 0, imageW: 0, imageH: 0, fillW: 0, fillH: 0, aspect: 0 };
    const fr = frame.getBoundingClientRect();
    const ir = image.getBoundingClientRect();
    return {
      frameW: fr.width,
      frameH: fr.height,
      imageW: ir.width,
      imageH: ir.height,
      fillW: fr.width > 0 ? ir.width / fr.width : 0,
      fillH: fr.height > 0 ? ir.height / fr.height : 0,
      aspect: fr.height > 0 ? fr.width / fr.height : 0,
    };
  });
}

function expectFillStable(
  baseline: Awaited<ReturnType<typeof measureFill>>,
  next: Awaited<ReturnType<typeof measureFill>>,
) {
  expect(next.frameW).toBeGreaterThan(80);
  expect(next.frameH).toBeGreaterThan(80);
  expect(next.aspect).toBeCloseTo(baseline.aspect, 2);
  expect(next.fillW).toBeCloseTo(baseline.fillW, 1);
  expect(next.fillH).toBeCloseTo(baseline.fillH, 1);
  expect(Math.min(next.fillW, next.fillH)).toBeGreaterThan(0.92);
}

test.describe("Rectangular Atlas + canonical placement grid", () => {
  test("circles, entities, transform isolation, and zoom-independent fill coexist", async ({ page, request }) => {
    const wide = await mapByTitle(request, MAP_16X9);
    const venture = await mapByTitle(request, MAP_VENTURE);
    const priorVenture = await getMap(request, venture.id);
    const priorChars = priorVenture.characters || [];
    const priorCams = priorVenture.cameras || [];
    expect(priorChars.length).toBeGreaterThanOrEqual(2);
    expect(priorCams.length).toBeGreaterThanOrEqual(1);

    let probe: { id: string; created: boolean } | null = null;
    try {
    await ensureWidePlate(request, wide.id);
    probe = await ensureProbeProp(request);
    await clearSandboxEntities(request, wide.id);
    await openMap(page, wide.id, MAP_16X9);

    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveAttribute("data-viewport", "rect");
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveAttribute("data-clip", "none");
    await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-clip", "none");
    expect(await page.locator("clipPath").count()).toBe(0);
    await expect(page.getByTestId("map-toggle-grid")).toBeVisible();
    await expect(page.getByTestId("map-toggle-circles")).toBeVisible();
    await expect(page.getByTestId("map-toggle-labels")).toBeVisible();
    const circleCount = await page.locator('[data-testid^="cell-circle-"]').count();
    expect(circleCount).toBeGreaterThan(8);

    await page.getByTestId("map-toggle-grid").click();
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveClass(/hide-grid/);
    await page.getByTestId("map-toggle-grid").click();
    await page.getByTestId("map-toggle-circles").click();
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveAttribute("data-circles", "off");
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveClass(/hide-circles/);
    await page.getByTestId("map-toggle-circles").click();
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveAttribute("data-circles", "on");
    await page.getByTestId("map-toggle-labels").click();
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveClass(/hide-labels/);
    await page.getByTestId("map-toggle-labels").click();

    await page.getByTestId("background-alignment-reset").click();
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-scale", "1");
    const fill100 = await measureFill(page);
    expect(Math.min(fill100.fillW, fill100.fillH)).toBeGreaterThan(0.92);
    const atlasScaleAtReset = await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-scale");

    await setWorkspaceZoom(page, 0.9);
    expectFillStable(fill100, await measureFill(page));
    await setWorkspaceZoom(page, 0.75);
    expectFillStable(fill100, await measureFill(page));
    await setWorkspaceZoom(page, 0.5);
    expectFillStable(fill100, await measureFill(page));
    await setWorkspaceZoom(page, 1);
    expectFillStable(fill100, await measureFill(page));
    expect(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-scale")).toBe(atlasScaleAtReset);

    await page.getByTestId("character-select-0").selectOption(KORRI_ID);
    await expect(page.getByTestId("placement-mode-banner")).toBeVisible({ timeout: 20_000 });
    const enabled = page.getByTestId("character-online-0");
    if ((await enabled.getAttribute("aria-checked")) !== "true") {
      await enabled.click();
    }
    await expect(enabled).toHaveAttribute("aria-checked", "true");
    await page.getByTestId("character-place-0").click();
    await expect(page.getByTestId("placement-mode-banner")).toBeVisible();
    const charPlaced = page.waitForResponse(
      (res) => res.url().includes("/characters/") && res.request().method() === "PATCH" && res.ok(),
    );
    await clickGridAt(page, 0.48, 0.52);
    await charPlaced;
    const characterMarker = page.locator("[data-testid^='placement-marker-'][data-kind='character']").first();
    await expect(characterMarker).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("character-move-0").click();
    await clickGridAt(page, 0.58, 0.56);
    await expect(characterMarker).toBeVisible();

    const propSelect = page.getByTestId("prop-select-0");
    await expect(propSelect.locator(`option[value="${probe!.id}"]`)).toBeAttached({ timeout: 20_000 });
    await propSelect.selectOption(probe!.id);
    await expect(page.getByTestId("prop-place-0")).toBeVisible({ timeout: 20_000 });
    const propEnabled = page.getByTestId("prop-online-0");
    await expect(propEnabled).toBeEnabled({ timeout: 20_000 });
    await expect(propEnabled).toHaveAttribute("aria-checked", "true");
    await page.getByTestId("prop-place-0").click();
    const propPlaced = page.waitForResponse(
      (res) => res.url().includes("/props/") && res.request().method() === "PATCH" && res.ok(),
    );
    await clickGridAt(page, 0.4, 0.6);
    await propPlaced;
    const propMarker = page.locator("[data-testid^='placement-marker-'][data-kind='prop']").first();
    await expect(propMarker).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("prop-move-0").click();
    await clickGridAt(page, 0.62, 0.48);
    await expect(propMarker).toBeVisible();

    await page.getByTestId("camera-add-0").click();
    await expect(page.getByTestId("camera-place-0")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("camera-place-0").click();
    const camPlaced = page.waitForResponse(
      (res) => res.url().includes("/cameras/") && res.request().method() === "PATCH" && res.ok(),
      { timeout: 15_000 },
    );
    await clickGridAt(page, 0.36, 0.46);
    const cameraMarker = page.locator("[data-testid^='camera-marker-']").first();
    await expect(cameraMarker).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("camera-move-0").click();
    await clickGridAt(page, 0.38, 0.5);
    await expect(cameraMarker).toBeVisible();

    const placed = await getMap(request, wide.id);
    const charBefore = placed.characters?.[0];
    const propBefore = placed.props?.[0];
    const camBefore = placed.cameras?.[0];
    expect(charBefore?.normalizedX).toEqual(expect.any(Number));
    expect(propBefore?.normalizedX).toEqual(expect.any(Number));
    expect(camBefore?.normalizedX).toEqual(expect.any(Number));

    const charBox = await characterMarker.boundingBox();
    const propBox = await propMarker.boundingBox();
    const camBox = await cameraMarker.boundingBox();
    await page.getByTestId("background-alignment-hand").click();
    const grid = page.getByTestId("spatial-map-grid");
    const box = await grid.boundingBox();
    expect(box).toBeTruthy();
    await grid.dragTo(grid, {
      sourcePosition: { x: box!.width / 2, y: box!.height / 2 },
      targetPosition: { x: box!.width / 2 + 36, y: box!.height / 2 + 16 },
    });
    await page.getByTestId("background-alignment-hand").click();
    const afterHand = await getMap(request, wide.id);
    expect(Number(afterHand.characters?.[0]?.normalizedX)).toBeCloseTo(Number(charBefore?.normalizedX), 5);
    expect(Number(afterHand.characters?.[0]?.normalizedY)).toBeCloseTo(Number(charBefore?.normalizedY), 5);
    expect(Number(afterHand.props?.[0]?.normalizedX)).toBeCloseTo(Number(propBefore?.normalizedX), 5);
    expect(Number(afterHand.cameras?.[0]?.normalizedX)).toBeCloseTo(Number(camBefore?.normalizedX), 5);
    const charAfterHand = await characterMarker.boundingBox();
    expect(Math.abs((charAfterHand?.x || 0) - (charBox?.x || 0))).toBeLessThan(8);
    expect(Math.abs((propMarker ? (await propMarker.boundingBox())?.x || 0 : 0) - (propBox?.x || 0))).toBeLessThan(8);
    expect(Math.abs((cameraMarker ? (await cameraMarker.boundingBox())?.x || 0 : 0) - (camBox?.x || 0))).toBeLessThan(8);

    if (await page.getByTestId("placement-mode-cancel").isVisible().catch(() => false)) {
      await page.getByTestId("placement-mode-cancel").click();
    }
    await page.getByTestId("background-alignment-resize").click();
    await expect(page.getByTestId("spatial-map-resize-handle-se")).toBeVisible({ timeout: 10_000 });
    const handle = page.getByTestId("spatial-map-resize-handle-se");
    const handleBox = await handle.boundingBox();
    expect(handleBox).toBeTruthy();
    await handle.hover();
    await page.mouse.down();
    await page.mouse.move(handleBox!.x + handleBox!.width / 2 + 40, handleBox!.y + handleBox!.height / 2 + 24, {
      steps: 12,
    });
    await page.mouse.up();
    const afterResize = await getMap(request, wide.id);
    expect(Number(afterResize.characters?.[0]?.normalizedX)).toBeCloseTo(Number(charBefore?.normalizedX), 5);
    expect(Number(afterResize.characters?.[0]?.normalizedY)).toBeCloseTo(Number(charBefore?.normalizedY), 5);
    expect(Number(afterResize.props?.[0]?.normalizedY)).toBeCloseTo(Number(propBefore?.normalizedY), 5);
    expect(Number(afterResize.cameras?.[0]?.normalizedY)).toBeCloseTo(Number(camBefore?.normalizedY), 5);

    await page.getByTestId("spatial-map-save").click();
    await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, { timeout: 20_000 });
    await page.goto(`/project/${PROJECT_ID}?workspace=library`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: /^Libraries$/ })).toBeVisible({ timeout: 30_000 });
    await openMap(page, wide.id, MAP_16X9);
    await expect(page.locator("[data-testid^='placement-marker-'][data-kind='character']")).toBeVisible();
    await expect(page.locator("[data-testid^='placement-marker-'][data-kind='prop']")).toBeVisible();
    await expect(page.locator("[data-testid^='camera-marker-']")).toBeVisible();
    const reloaded = await getMap(request, wide.id);
    expect(Number(reloaded.characters?.[0]?.normalizedX)).toBeCloseTo(Number(charBefore?.normalizedX), 5);
    expect(Number(reloaded.characters?.[0]?.normalizedY)).toBeCloseTo(Number(charBefore?.normalizedY), 5);
    expect(Number(reloaded.props?.[0]?.normalizedX)).toBeCloseTo(Number(propBefore?.normalizedX), 5);
    expect(Number(reloaded.cameras?.[0]?.normalizedX)).toBeCloseTo(Number(camBefore?.normalizedX), 5);
    expect(Number(reloaded.backgroundAlignment?.sourceWidth)).toBe(1280);
    expect(Number(reloaded.backgroundAlignment?.sourceHeight)).toBe(720);

    await openMap(page, venture.id, "Venture Corridor Walk");
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveAttribute("data-viewport", "rect");
    await expect(page.getByTestId("map-toggle-circles")).toBeVisible();
    expect(await page.locator('[data-testid^="cell-circle-"]').count()).toBeGreaterThan(8);
    expect(await page.locator("[data-testid^='placement-marker-']").count()).toBeGreaterThanOrEqual(2);
    expect(await page.locator("[data-testid^='camera-marker-']").count()).toBeGreaterThanOrEqual(1);
    await page.getByTestId("background-alignment-reset").click();
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-scale", "1");
    const ventureFill = await measureFill(page);
    expect(Math.min(ventureFill.fillW, ventureFill.fillH)).toBeGreaterThan(0.92);
    await setWorkspaceZoom(page, 0.75);
    expectFillStable(ventureFill, await measureFill(page));
    await setWorkspaceZoom(page, 0.5);
    expectFillStable(ventureFill, await measureFill(page));
    await setWorkspaceZoom(page, 1);
    const afterVentureUi = await getMap(request, venture.id);
    for (let i = 0; i < priorChars.length; i += 1) {
      expect(Number(afterVentureUi.characters?.[i]?.normalizedX)).toBeCloseTo(Number(priorChars[i]?.normalizedX), 5);
      expect(Number(afterVentureUi.characters?.[i]?.normalizedY)).toBeCloseTo(Number(priorChars[i]?.normalizedY), 5);
    }
    for (let i = 0; i < priorCams.length; i += 1) {
      expect(Number(afterVentureUi.cameras?.[i]?.normalizedX)).toBeCloseTo(Number(priorCams[i]?.normalizedX), 5);
      expect(Number(afterVentureUi.cameras?.[i]?.normalizedY)).toBeCloseTo(Number(priorCams[i]?.normalizedY), 5);
    }

    } finally {
      await clearSandboxEntities(request, wide.id);
      if (probe?.created) {
        await request.delete(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/props/${probe.id}`);
      }
    }
  });
});
