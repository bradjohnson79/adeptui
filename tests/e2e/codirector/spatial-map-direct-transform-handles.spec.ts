/**
 * Photoshop-style on-canvas transform handles.
 * Reuses Korri Native Aspect 16:9 and 4:3. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";

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
};

const CASES = [
  { title: "Native Aspect 16:9", aspect: 16 / 9, width: 1280, height: 720 },
  { title: "Native Aspect 4:3", aspect: 4 / 3, width: 800, height: 600 },
] as const;

async function listMaps(request: APIRequestContext): Promise<MapDoc[]> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), "list Spatial Maps").toBeTruthy();
  return ((await res.json()).documents || []) as MapDoc[];
}

async function openMap(page: Page, mapId: string, title: string) {
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
  const heading = page.getByRole("heading", { name: title });
  if (!(await heading.isVisible().catch(() => false))) {
    await page.goto(`/project/${PROJECT_ID}?workspace=spatial`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    await page.locator("#spatial-map-select").selectOption(mapId);
    await expect(page.locator("#spatial-map-select")).toHaveValue(mapId, { timeout: 15_000 });
  }
  await expect(page.getByRole("heading", { name: title })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("spatial-map-atlas-layer")).toBeVisible({ timeout: 20_000 });
}

async function dragHandle(page: Page, corner: "se" | "nw", dx: number, dy: number) {
  const handle = page.getByTestId(`spatial-map-resize-handle-${corner}`);
  await expect(handle).toBeVisible();
  await handle.scrollIntoViewIfNeeded();
  const box = await handle.boundingBox();
  expect(box).toBeTruthy();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-resize-dragging", "true", {
    timeout: 5_000,
  });
  await page.mouse.move(box!.x + box!.width / 2 + dx, box!.y + box!.height / 2 + dy, { steps: 16 });
  await page.mouse.up();
}

test.describe("Spatial Map direct transform handles", () => {
  for (const spec of CASES) {
    test(`${spec.title} bbox handles resize, move, and persist`, async ({ page, request }) => {
      const map = (await listMaps(request)).find((item) => item.title === spec.title);
      expect(map, spec.title).toBeTruthy();

      await openMap(page, map!.id, spec.title);
      const atlas = page.getByTestId("spatial-map-atlas-layer");
      await expect
        .poll(async () => Number(await atlas.getAttribute("data-source-width")), { timeout: 20_000 })
        .toBe(spec.width);
      await expect
        .poll(async () => Number(await atlas.getAttribute("data-aspect")), { timeout: 20_000 })
        .toBeCloseTo(spec.aspect, 2);

      await expect(page.locator("#spatial-map-select")).toHaveValue(map!.id);
      await page.getByTestId("background-alignment-reset").click();
      await expect(page.locator("#spatial-map-select")).toHaveValue(map!.id);
      await expect(page.getByRole("heading", { name: spec.title })).toBeVisible();
      await expect.poll(async () => Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-scale"))).toBeCloseTo(1, 2);
      await expect.poll(async () => Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-x"))).toBeCloseTo(0, 2);
      await expect.poll(async () => Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-y"))).toBeCloseTo(0, 2);

      const grid = page.getByTestId("spatial-map-grid");
      await expect(grid).toBeVisible();
      await grid.scrollIntoViewIfNeeded();
      const viewBox = await grid.boundingBox();
      expect(viewBox).toBeTruthy();
      await page.mouse.click(
        viewBox!.x + viewBox!.width / 2,
        viewBox!.y + Math.min(viewBox!.height / 2, 180),
      );
      if ((await grid.getAttribute("data-map-selected")) !== "true") {
        await page.getByTestId("background-alignment-resize").click();
      }
      await expect(grid).toHaveAttribute("data-map-selected", "true");
      await page.getByTestId("map-zoom-out").click();
      await expect(page.getByTestId("spatial-map-viewport")).toHaveAttribute("data-zoom", "0.75");
      await expect(page.getByTestId("spatial-map-transform-box")).toBeVisible();
      await expect(page.getByTestId("spatial-map-resize-handle-nw")).toBeVisible();
      await expect(page.getByTestId("spatial-map-resize-handle-ne")).toBeVisible();
      await expect(page.getByTestId("spatial-map-resize-handle-sw")).toBeVisible();
      await expect(page.getByTestId("spatial-map-resize-handle-se")).toBeVisible();

      const startScale = Number(await atlas.getAttribute("data-scale"));
      const gridPath = await page.getByTestId("spatial-map-grid-lines").getAttribute("d");

      await dragHandle(page, "se", 70, 70);
      const afterSe = Number(await atlas.getAttribute("data-scale"));
      expect(afterSe).toBeGreaterThan(startScale + 0.04);
      expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(spec.aspect, 2);
      expect(await page.getByTestId("spatial-map-grid-lines").getAttribute("d")).toBe(gridPath);

      await dragHandle(page, "nw", 28, 28);
      const afterNw = Number(await atlas.getAttribute("data-scale"));
      expect(afterNw).toBeLessThan(afterSe);
      expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(spec.aspect, 2);

      await page.getByTestId("background-alignment-hand").click();
      const box = await grid.boundingBox();
      expect(box).toBeTruthy();
      await grid.dragTo(grid, {
        sourcePosition: { x: box!.width / 2, y: box!.height / 2 },
        targetPosition: { x: box!.width / 2 + 26, y: box!.height / 2 + 12 },
      });
      expect(Number(await atlas.getAttribute("data-scale"))).toBeCloseTo(afterNw, 2);
      expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(spec.aspect, 2);
      expect(Number(await atlas.getAttribute("data-offset-x"))).not.toBe(0);

      await dragHandle(page, "se", 22, 22);
      const afterAgain = Number(await atlas.getAttribute("data-scale"));
      expect(afterAgain).toBeGreaterThan(afterNw);
      expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(spec.aspect, 2);

      await page.getByTestId("spatial-map-save").click();
      await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, { timeout: 20_000 });
      const savedOffsetX = Number(await atlas.getAttribute("data-offset-x"));
      const savedOffsetY = Number(await atlas.getAttribute("data-offset-y"));

      await page.goto(`/project/${PROJECT_ID}?workspace=library`, { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: /^Libraries$/ })).toBeVisible({ timeout: 30_000 });
      await openMap(page, map!.id, spec.title);
      await expect
        .poll(async () => Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-scale")))
        .toBeCloseTo(afterAgain, 2);
      expect(Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-aspect"))).toBeCloseTo(
        spec.aspect,
        2,
      );
      expect(Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-x"))).toBeCloseTo(
        savedOffsetX,
        2,
      );
      expect(Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-offset-y"))).toBeCloseTo(
        savedOffsetY,
        2,
      );

      const live = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${map!.id}`);
      const doc = ((await live.json()).document || {}) as MapDoc;
      expect(Number(doc.backgroundAlignment?.sourceWidth)).toBe(spec.width);
      expect(Number(doc.backgroundAlignment?.sourceHeight)).toBe(spec.height);
      expect(Number(doc.backgroundAlignment?.sourceAspectRatio)).toBeCloseTo(spec.aspect, 2);
      expect(Number(doc.backgroundAlignment?.scale)).toBeCloseTo(afterAgain, 2);
    });
  }
});
