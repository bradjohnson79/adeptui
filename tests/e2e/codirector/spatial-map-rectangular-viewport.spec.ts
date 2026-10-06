/**
 * Spatial Map rectangular native-aspect workspace.
 * Reuses Korri maps titled Native Aspect 4:3 / 16:9 and Venture Corridor Walk.
 * Never POST /api/projects. Never accept Reset Map on Venture.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const MAP_4X3 = "Native Aspect 4:3";
const MAP_16X9 = "Native Aspect 16:9";
const MAP_VENTURE = /venture corridor walk/i;

test.setTimeout(6 * 60 * 1000);

type MapDoc = {
  id: string;
  title?: string;
  backgroundAlignment?: {
    offsetX?: number;
    offsetY?: number;
    scale?: number;
    sourceWidth?: number;
    sourceHeight?: number;
    sourceAspectRatio?: number;
  };
  characters?: Array<{ normalizedX?: number; normalizedY?: number }>;
  cameras?: Array<{ normalizedX?: number; normalizedY?: number }>;
};

async function listMaps(request: APIRequestContext): Promise<MapDoc[]> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), "list Spatial Maps").toBeTruthy();
  const body = await res.json();
  return (body.documents || []) as MapDoc[];
}

async function mapByTitle(request: APIRequestContext, title: string | RegExp): Promise<MapDoc> {
  const maps = await listMaps(request);
  const found = maps.find((m) =>
    typeof title === "string" ? m.title === title : title.test(String(m.title || "")),
  );
  expect(found, `map ${String(title)}`).toBeTruthy();
  return found!;
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

async function assertRectangularViewport(page: Page, aspect: number) {
  const frame = page.getByTestId("spatial-map-viewport-frame");
  await expect(frame).toHaveAttribute("data-viewport", "rect");
  await expect(frame).toHaveAttribute("data-clip", "none");
  const radius = await frame.evaluate((el) => getComputedStyle(el).borderRadius);
  expect(radius === "50%" || radius === "9999px").toBeFalsy();

  const grid = page.getByTestId("spatial-map-grid");
  await expect(grid).toHaveAttribute("data-viewport", "rect");
  await expect(grid).toHaveAttribute("data-clip", "none");
  await expect(grid).toHaveAttribute("preserveAspectRatio", "xMidYMid slice");
  expect(await grid.locator("clipPath").count()).toBe(0);
  expect(await page.locator(".spatial-map__circle-stroke").count()).toBe(0);
  await expect(page.getByTestId("map-toggle-grid")).toBeVisible();
  await expect(page.getByTestId("map-toggle-circles")).toBeVisible();
  await expect(page.getByTestId("map-toggle-labels")).toBeVisible();
  await expect(page.getByTestId("spatial-map-placement-grid-layer")).toBeVisible();
  expect(await page.locator('[data-testid^="cell-circle-"]').count()).toBeGreaterThan(8);

  const atlas = page.getByTestId("spatial-map-atlas-layer");
  await expect(atlas).toHaveAttribute("data-fit", "contain", { timeout: 20_000 });
  await expect
    .poll(async () => Number(await atlas.getAttribute("data-aspect")), { timeout: 20_000 })
    .toBeCloseTo(aspect, 2);
  const imgW = Number(await atlas.getAttribute("data-image-width"));
  const imgH = Number(await atlas.getAttribute("data-image-height"));
  expect(imgW / imgH).toBeCloseTo(aspect, 2);
  expect(Math.abs(imgW - imgH)).toBeGreaterThan(8);
}

test.describe("Spatial Map rectangular native-aspect workspace", () => {
  test("16:9 and 4:3 stay rectangular; calibration and placements persist", async ({ page, request }) => {
    const wide = await mapByTitle(request, MAP_16X9);
    const four = await mapByTitle(request, MAP_4X3);
    const venture = await mapByTitle(request, MAP_VENTURE);

    await openMap(page, wide.id, MAP_16X9);
    await assertRectangularViewport(page, 16 / 9);

    const grid = page.getByTestId("spatial-map-grid");
    const startGridSize = await grid.getAttribute("data-grid-size");
    const startScale = await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-scale");
    const zoom = page.getByTestId("spatial-map-viewport");
    const startZoom = await zoom.getAttribute("data-zoom");

    const frame = page.getByTestId("spatial-map-viewport-frame");
    const startFrameW = (await frame.boundingBox())?.width || 0;
    await page.getByTestId("map-zoom-in").click();
    await expect(zoom).not.toHaveAttribute("data-zoom", String(startZoom));
    await expect
      .poll(async () => (await frame.boundingBox())?.width || 0, { timeout: 10_000 })
      .toBeGreaterThan(startFrameW + 8);
    await expect(grid).toHaveAttribute("data-grid-size", String(startGridSize));
    expect(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-scale")).toBe(startScale);

    const pathAfterZoom = await page.getByTestId("spatial-map-grid-lines").getAttribute("d");
    await page.getByTestId("background-alignment-resize").click();
    await page.getByTestId("background-alignment-scale").fill("125");
    await page.getByTestId("background-alignment-scale").blur();
    const atlas = page.getByTestId("spatial-map-atlas-layer");
    await expect(atlas).toHaveAttribute("data-scale", /1\.25/);
    expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(16 / 9, 2);
    expect(await page.getByTestId("spatial-map-grid-lines").getAttribute("d")).toBe(pathAfterZoom);
    await page.getByTestId("background-alignment-resize").click();

    await page.getByTestId("background-alignment-hand").click();
    const box = await grid.boundingBox();
    expect(box).toBeTruthy();
    await grid.dragTo(grid, {
      sourcePosition: { x: box!.width / 2, y: box!.height / 2 },
      targetPosition: { x: box!.width / 2 + 30, y: box!.height / 2 + 14 },
    });
    expect(Number(await atlas.getAttribute("data-scale"))).toBeCloseTo(1.25, 2);
    expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(16 / 9, 2);
    expect(Number(await atlas.getAttribute("data-offset-x"))).not.toBe(0);
    await page.getByTestId("background-alignment-hand").click();

    await page.getByTestId("spatial-map-save").click();
    await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, { timeout: 20_000 });

    await page.goto(`/project/${PROJECT_ID}?workspace=library`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: /^Libraries$/ })).toBeVisible({ timeout: 30_000 });
    await openMap(page, wide.id, MAP_16X9);
    await assertRectangularViewport(page, 16 / 9);
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-scale", /1\.25/);

    const liveWide = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${wide.id}`);
    const wideDoc = ((await liveWide.json()).document || {}) as MapDoc;
    expect(Number(wideDoc.backgroundAlignment?.sourceWidth)).toBe(1280);
    expect(Number(wideDoc.backgroundAlignment?.sourceHeight)).toBe(720);
    expect(Number(wideDoc.backgroundAlignment?.sourceAspectRatio)).toBeCloseTo(16 / 9, 2);
    expect(Number(wideDoc.backgroundAlignment?.scale)).toBeCloseTo(1.25, 2);

    await openMap(page, four.id, MAP_4X3);
    await assertRectangularViewport(page, 4 / 3);
    const liveFour = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${four.id}`);
    const fourDoc = ((await liveFour.json()).document || {}) as MapDoc;
    expect(Number(fourDoc.backgroundAlignment?.sourceWidth)).toBe(800);
    expect(Number(fourDoc.backgroundAlignment?.sourceHeight)).toBe(600);
    expect(Number(fourDoc.backgroundAlignment?.sourceAspectRatio)).toBeCloseTo(4 / 3, 2);

    const beforeVenture = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${venture.id}`);
    const prior = ((await beforeVenture.json()).document || {}) as MapDoc;
    await openMap(page, venture.id, "Venture Corridor Walk");
    await expect(page.getByTestId("spatial-map-viewport-frame")).toHaveAttribute("data-viewport", "rect");
    await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-clip", "none");
    const markers = page.locator("[data-testid^='placement-marker-']");
    const cameras = page.locator("[data-testid^='camera-marker-']");
    expect((await markers.count()) + (await cameras.count())).toBeGreaterThanOrEqual(3);

    const afterVenture = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${venture.id}`);
    const next = ((await afterVenture.json()).document || {}) as MapDoc;
    const priorChars = prior.characters || [];
    const nextChars = next.characters || [];
    expect(nextChars.length).toBe(priorChars.length);
    for (let i = 0; i < priorChars.length; i += 1) {
      expect(Number(nextChars[i]?.normalizedX)).toBeCloseTo(Number(priorChars[i]?.normalizedX), 5);
      expect(Number(nextChars[i]?.normalizedY)).toBeCloseTo(Number(priorChars[i]?.normalizedY), 5);
    }
    const priorCams = prior.cameras || [];
    const nextCams = next.cameras || [];
    expect(nextCams.length).toBe(priorCams.length);
    for (let i = 0; i < priorCams.length; i += 1) {
      expect(Number(nextCams[i]?.normalizedX)).toBeCloseTo(Number(priorCams[i]?.normalizedX), 5);
      expect(Number(nextCams[i]?.normalizedY)).toBeCloseTo(Number(priorCams[i]?.normalizedY), 5);
    }
  });
});
