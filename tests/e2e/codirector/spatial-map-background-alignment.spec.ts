/**
 * Spatial Map Background Alignment — Standard workspace.
 * Named Korri project + Venture Corridor Walk only. Never creates a project.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const MAP_TITLE = /venture corridor walk/i;

test.setTimeout(6 * 60 * 1000);

type MapDoc = {
  id: string;
  title?: string;
  backgroundAssetId?: string | null;
  backgroundAlignment?: { offsetX?: number; offsetY?: number; scale?: number };
  characters?: Array<Record<string, unknown>>;
  props?: Array<Record<string, unknown>>;
  cameras?: Array<Record<string, unknown>>;
  movementSegments?: Array<Record<string, unknown>>;
  activeMovementSegmentId?: string | null;
};

async function listMaps(request: APIRequestContext): Promise<MapDoc[]> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), "list Spatial Maps").toBeTruthy();
  const body = await res.json();
  return (body.documents || body.maps || body.items || []) as MapDoc[];
}

async function resolveVentureMap(request: APIRequestContext): Promise<MapDoc> {
  const maps = await listMaps(request);
  const venture = maps.find((m) => MAP_TITLE.test(String(m.title || "")));
  expect(venture, "Venture Corridor Walk must exist on the Korri project").toBeTruthy();
  return venture!;
}

async function mapDocument(request: APIRequestContext, mapId: string): Promise<MapDoc> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
  expect(res.ok(), `GET map ${mapId}`).toBeTruthy();
  const body = await res.json();
  return (body.document || body) as MapDoc;
}

async function patchAlignment(
  request: APIRequestContext,
  mapId: string,
  offsetX: number,
  offsetY: number,
  scale = 1,
) {
  const res = await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`, {
    data: { backgroundAlignment: { offsetX, offsetY, scale } },
  });
  expect(res.ok(), "PATCH backgroundAlignment").toBeTruthy();
  return res.json();
}

async function openStandardSpatial(page: Page) {
  await page.goto(`/project/${PROJECT_ID}?workspace=spatial`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

async function selectMap(page: Page, mapId: string) {
  const select = page.locator("#spatial-map-select");
  if ((await select.count()) && (await select.isVisible().catch(() => false))) {
    await select.selectOption(mapId);
    await expect(select).toHaveValue(mapId, { timeout: 15_000 });
  }
  await expect(page.getByTestId("spatial-map-grid")).toBeVisible({ timeout: 20_000 });
}

function entitySnapshot(doc: MapDoc) {
  const pick = (item: Record<string, unknown>) => ({
    id: item.id,
    normalizedX: item.normalizedX,
    normalizedY: item.normalizedY,
    gridRow: item.gridRow,
    gridColumn: item.gridColumn,
    yawDegrees: item.yawDegrees,
    visible: item.visible,
  });
  return {
    backgroundAssetId: doc.backgroundAssetId || null,
    characters: (doc.characters || []).map(pick),
    props: (doc.props || []).map(pick),
    cameras: (doc.cameras || []).map(pick),
    movementIds: (doc.movementSegments || []).map((s) => s.id),
    activeMovementSegmentId: doc.activeMovementSegmentId || null,
  };
}

test.describe("Spatial Map background alignment", () => {
  let originalAlignment = { offsetX: 0, offsetY: 0, scale: 1 };
  let mapId = "";
  let atlasId: string | null = null;

  test.beforeAll(async ({ request }) => {
    const venture = await resolveVentureMap(request);
    mapId = venture.id;
    const live = await mapDocument(request, mapId);
    atlasId = live.backgroundAssetId || null;
    originalAlignment = {
      offsetX: Number(live.backgroundAlignment?.offsetX || 0),
      offsetY: Number(live.backgroundAlignment?.offsetY || 0),
      scale: Number(live.backgroundAlignment?.scale ?? 1) || 1,
    };
  });

  test.afterEach(async ({ request }) => {
    if (!mapId) return;
    await patchAlignment(
      request,
      mapId,
      originalAlignment.offsetX,
      originalAlignment.offsetY,
      originalAlignment.scale,
    ).catch(() => undefined);
    if (atlasId) {
      const live = await mapDocument(request, mapId);
      expect(live.backgroundAssetId).toBe(atlasId);
    }
  });

  test("Hand Tool pans Atlas only; X/Y, Reset, Save, navigate, reload persist", async ({
    page,
    request,
  }) => {
    const before = await mapDocument(request, mapId);
    const beforeEntities = entitySnapshot(before);
    expect(before.backgroundAssetId).toBeTruthy();

    await openStandardSpatial(page);
    await selectMap(page, mapId);
    await expect(page.getByTestId("background-alignment")).toBeVisible({ timeout: 20_000 });

    const precisionBox = await page.getByTestId("placement-precision-control").boundingBox();
    const alignBox = await page.getByTestId("background-alignment").boundingBox();
    const controlsBox = await page.getByTestId("map-controls").boundingBox();
    expect(precisionBox && alignBox && controlsBox).toBeTruthy();
    expect(alignBox!.y).toBeGreaterThan(precisionBox!.y);
    expect(controlsBox!.y).toBeGreaterThan(alignBox!.y);

    const help = page.getByTestId("background-alignment-help").locator("button").first();
    await help.hover();
    await expect(page.getByRole("tooltip")).toContainText(
      /Click the Spatial Map picture to select it/i,
      { timeout: 5_000 },
    );
    await page.keyboard.press("Escape");

    const gridLines = page.getByTestId("spatial-map-grid-lines");
    const atlasLayer = page.getByTestId("spatial-map-atlas-layer");
    await expect(atlasLayer).toBeVisible();
    const gridPathBefore = await gridLines.getAttribute("d");
    const marker = page.locator('[data-testid^="placement-marker-"]').first();
    const markerTransformBefore = (await marker.count()) ? await marker.getAttribute("transform") : null;
    const atlasTransformBefore = await atlasLayer.getAttribute("transform");

    await page.getByTestId("background-alignment-hand").click();
    await expect(page.getByTestId("background-alignment-hand")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-hand-active", "true");
    const grid = page.getByTestId("spatial-map-grid");
    const box = await grid.boundingBox();
    expect(box).toBeTruthy();
    await grid.dragTo(grid, {
      sourcePosition: { x: box!.width / 2, y: box!.height / 2 },
      targetPosition: { x: box!.width / 2 + 48, y: box!.height / 2 + 28 },
    });

    expect(await gridLines.getAttribute("d")).toBe(gridPathBefore);
    if (markerTransformBefore) {
      expect(await marker.getAttribute("transform")).toBe(markerTransformBefore);
    }
    expect(await atlasLayer.getAttribute("transform")).not.toBe(atlasTransformBefore);
    const draggedOffsetX = Number(await atlasLayer.getAttribute("data-offset-x"));
    const draggedOffsetY = Number(await atlasLayer.getAttribute("data-offset-y"));
    expect(Math.abs(draggedOffsetX) + Math.abs(draggedOffsetY)).toBeGreaterThan(0);

    await page.getByTestId("background-alignment-hand").click();
    await expect(page.getByTestId("background-alignment-hand")).toHaveAttribute("aria-pressed", "false");

    await page.getByTestId("background-alignment-x").fill("-24");
    await page.getByTestId("background-alignment-y").fill("12");
    await page.getByTestId("background-alignment-y").blur();
    await expect(page.getByTestId("spatial-map-save-state")).toContainText(/Unsaved changes/i, {
      timeout: 10_000,
    });
    await page.getByTestId("spatial-map-save").click();
    await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, {
      timeout: 20_000,
    });

    const afterEdit = await mapDocument(request, mapId);
    expect(entitySnapshot(afterEdit)).toEqual(beforeEntities);
    expect(afterEdit.backgroundAlignment?.offsetX).not.toBe(0);

    await page.goto(`/project/${PROJECT_ID}?workspace=timeline`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await openStandardSpatial(page);
    await selectMap(page, mapId);
    await expect(page.getByTestId("background-alignment")).toBeVisible({ timeout: 20_000 });
    const returnedOffset = Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-x"));
    expect(returnedOffset).toBeCloseTo(Number(afterEdit.backgroundAlignment?.offsetX), 5);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    await selectMap(page, mapId);
    const reloadedOffset = Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-x"));
    expect(reloadedOffset).toBeCloseTo(Number(afterEdit.backgroundAlignment?.offsetX), 5);

    await page.getByTestId("background-alignment-reset").click();
    await page.getByTestId("spatial-map-save").click();
    await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, {
      timeout: 20_000,
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    await selectMap(page, mapId);
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-offset-x", "0");
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-offset-y", "0");

    const restored = await mapDocument(request, mapId);
    expect(restored.backgroundAlignment?.offsetX || 0).toBe(0);
    expect(restored.backgroundAlignment?.offsetY || 0).toBe(0);
    expect(Number(restored.backgroundAlignment?.scale ?? 1)).toBe(1);
    expect(entitySnapshot(restored)).toEqual(beforeEntities);
  });

  test("Resize then Freehand Align persist; Reset Alignment restores {0,0,1}", async ({
    page,
    request,
  }) => {
    const before = await mapDocument(request, mapId);
    const beforeEntities = entitySnapshot(before);
    expect(before.backgroundAssetId).toBeTruthy();
    const placed = [
      ...(before.characters || []),
      ...(before.cameras || []),
    ].filter((item) => item.normalizedX != null && item.normalizedY != null);
    expect(placed.length, "Venture must keep at least one placed character or camera").toBeGreaterThan(0);

    await openStandardSpatial(page);
    await selectMap(page, mapId);
    await expect(page.getByTestId("background-alignment-resize")).toBeVisible({ timeout: 20_000 });

    await page.getByTestId("map-zoom-out").click();
    await expect(page.getByTestId("spatial-map-viewport")).toHaveAttribute("data-zoom", "0.75");

    const gridLines = page.getByTestId("spatial-map-grid-lines");
    const atlasLayer = page.getByTestId("spatial-map-atlas-layer");
    const gridPathBefore = await gridLines.getAttribute("d");
    const marker = page.locator('[data-testid^="placement-marker-"]').first();
    const markerTransformBefore = (await marker.count()) ? await marker.getAttribute("transform") : null;
    const workspaceZoom = await page.getByTestId("spatial-map-viewport").getAttribute("data-zoom");

    await page.getByTestId("background-alignment-resize").click();
    await expect(page.getByTestId("background-alignment-resize")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-resize-active", "true");
    await expect(page.getByTestId("background-alignment-hand")).toHaveAttribute("aria-pressed", "false");

    const se = page.getByTestId("spatial-map-resize-handle-se");
    await expect(se).toBeVisible();
    await page.getByTestId("spatial-map-grid").scrollIntoViewIfNeeded();
    const handleBox = await se.boundingBox();
    expect(handleBox).toBeTruthy();
    const startScale = Number(await atlasLayer.getAttribute("data-scale"));
    await se.dragTo(se, {
      force: true,
      sourcePosition: { x: handleBox!.width / 2, y: handleBox!.height / 2 },
      targetPosition: { x: handleBox!.width / 2 + 48, y: handleBox!.height / 2 + 48 },
    });

    expect(await gridLines.getAttribute("d")).toBe(gridPathBefore);
    if (markerTransformBefore) {
      expect(await marker.getAttribute("transform")).toBe(markerTransformBefore);
    }
    expect(await page.getByTestId("spatial-map-viewport").getAttribute("data-zoom")).toBe(workspaceZoom);
    const enlarged = Number(await atlasLayer.getAttribute("data-scale"));
    expect(enlarged).toBeGreaterThan(startScale + 0.03);

    await page.getByTestId("background-alignment-resize").click();
    await expect(page.getByTestId("background-alignment-resize")).toHaveAttribute("aria-pressed", "false");

    await page.getByTestId("background-alignment-hand").click();
    const grid = page.getByTestId("spatial-map-grid");
    const box = await grid.boundingBox();
    expect(box).toBeTruthy();
    await grid.dragTo(grid, {
      sourcePosition: { x: box!.width / 2, y: box!.height / 2 },
      targetPosition: { x: box!.width / 2 + 36, y: box!.height / 2 + 20 },
    });
    const afterAlignScale = Number(await atlasLayer.getAttribute("data-scale"));
    expect(afterAlignScale).toBeCloseTo(enlarged, 3);
    expect(Number(await atlasLayer.getAttribute("data-offset-x"))).not.toBe(0);

    await page.getByTestId("background-alignment-hand").click();
    await page.getByTestId("background-alignment-resize").click();
    await page.getByTestId("background-alignment-scale").fill("140");
    await page.getByTestId("background-alignment-scale").blur();
    await expect(atlasLayer).toHaveAttribute("data-scale", /1\.4/);
    expect(Number(await atlasLayer.getAttribute("data-offset-x"))).not.toBe(0);

    await page.getByTestId("background-alignment-resize").click();
    await page.getByTestId("background-alignment-hand").click();
    await grid.dragTo(grid, {
      sourcePosition: { x: box!.width / 2, y: box!.height / 2 },
      targetPosition: { x: box!.width / 2 - 16, y: box!.height / 2 - 10 },
    });
    await page.getByTestId("background-alignment-hand").click();

    await page.getByTestId("spatial-map-save").click();
    await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, {
      timeout: 20_000,
    });

    const afterEdit = await mapDocument(request, mapId);
    expect(entitySnapshot(afterEdit)).toEqual(beforeEntities);
    expect(Number(afterEdit.backgroundAlignment?.scale)).toBeCloseTo(1.4, 2);
    expect(afterEdit.backgroundAlignment?.offsetX).not.toBe(0);
    expect(afterEdit.backgroundAssetId).toBe(before.backgroundAssetId);

    await page.goto(`/project/${PROJECT_ID}?workspace=timeline`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await openStandardSpatial(page);
    await selectMap(page, mapId);
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-scale", /1\.4/);
    const returnedOffset = Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-x"));
    expect(returnedOffset).toBeCloseTo(Number(afterEdit.backgroundAlignment?.offsetX), 5);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    await selectMap(page, mapId);
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-scale", /1\.4/);
    const reloadedOffset = Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-x"));
    expect(reloadedOffset).toBeCloseTo(Number(afterEdit.backgroundAlignment?.offsetX), 5);

    // Calibration reset only — do not click Reset Map (that still confirms and clears placements).
    await page.getByTestId("background-alignment-reset").click();
    await page.getByTestId("spatial-map-save").click();
    await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, {
      timeout: 20_000,
    });
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-offset-x", "0");
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-offset-y", "0");
    await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-scale", "1");

    const restored = await mapDocument(request, mapId);
    expect(restored.backgroundAlignment?.offsetX || 0).toBe(0);
    expect(restored.backgroundAlignment?.offsetY || 0).toBe(0);
    expect(Number(restored.backgroundAlignment?.scale ?? 1)).toBe(1);
    expect(restored.backgroundAssetId).toBe(before.backgroundAssetId);
    expect(entitySnapshot(restored)).toEqual(beforeEntities);
  });
});
