/**
 * Playwright E2E — Spatial Map Cartesian precision grid + entity blocking.
 *
 * Live Beta: ADEPT_BETA_TARGET=1 → http://127.0.0.1:8760 + API :8761
 *
 * A Default 10×10 Cartesian grid (no radial rings)
 * B Placement Precision −5..+5 with visible density change
 * C Character: saved dropdown → Add → Place → one-cell Move → reload
 * D Prop: same chain
 * E Camera C1: Place, NE, Wide, one-cell Move, reload
 * F Position stability across Neutral / +5 / -5 / Neutral
 * G Mixed blocking screenshot
 */
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "./helpers/app";
import { AuditObserver } from "./helpers/observer";
import { openCoDirectorFullScreen } from "./codirector/helpers/audit";

const PROJECT_PREFIX = "SPATIAL-CARTESIAN";
const SCREENSHOT_DIR = path.join("tests", "e2e", "screenshots", "spatial-map");
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8761";
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);

async function createCharacter(request: APIRequestContext, projectId: string, name: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/characters`, { data: { name } });
  expect(res.ok(), `createCharacter failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}

async function createCharacterProp(request: APIRequestContext, projectId: string, characterId: string, name: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/characters/${characterId}/props`, {
    data: { name },
  });
  expect(res.ok(), `createCharacterProp failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string; name: string };
}

async function uploadAtlasImage(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: "atlas.png", mimeType: "image/png", buffer: TINY_PNG },
      tag: "atlas_shot",
      kind: "image",
    },
  });
  expect(res.ok(), `uploadAtlasImage failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}

async function createSpatialMap(request: APIRequestContext, projectId: string, backgroundAssetId: string) {
  const res = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps`, {
    data: { title: "Spatial Map Cartesian Test", backgroundAssetId },
  });
  expect(res.ok(), `createSpatialMap failed: ${await res.text()}`).toBeTruthy();
}

async function openSpatialMapTab(page: Page) {
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    const panel = page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first();
    if (await panel.isVisible().catch(() => false)) return;
    await page.waitForTimeout(1000);
  }
  await expect(page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first()).toBeVisible({
    timeout: 45_000,
  });
}



async function openAndCloseAtlasModal(page: Page) {
  await expect(page.getByTestId("active-atlas-panel")).toBeVisible();
  await page.getByTestId("atlas-replace-btn").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("environment-picker-search")).toBeVisible();
  await expect(page.getByTestId("environment-picker-cancel")).toBeVisible();
  await expect(page.getByTestId("environment-picker-confirm")).toBeVisible();
  await page.getByTestId("environment-picker-cancel").click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("active-atlas-panel")).toBeVisible();

  await page.getByTestId("atlas-replace-btn").click();
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await page.locator('[data-testid^="environment-asset-"]').first().click();
  await expect(page.getByTestId("environment-picker-confirm")).toBeEnabled();
  await page.getByTestId("environment-picker-confirm").click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible();
  await expect(page.getByTestId("active-atlas-panel")).toBeVisible();
}

async function clickGridCell(page: Page, column: number, row: number) {
  const svg = page.getByTestId("spatial-map-grid");
  await expect(svg).toBeVisible();
  const box = await svg.boundingBox();
  if (!box) throw new Error("grid svg not found");
  const density = Number(await svg.getAttribute("data-grid-size"));
  const cell = box.width / density;
  await svg.click({ position: { x: (column + 0.5) * cell, y: (row + 0.5) * cell } });
}

async function setPrecision(page: Page, targetScale: number) {
  const current = await page.getByTestId("grid-scale-value").textContent();
  const parsed = current?.includes("Neutral") ? 0 : parseInt((current || "0").replace("×", "x").split(" ")[0].replace("+", ""), 10);
  if (Number.isNaN(parsed)) throw new Error(`Cannot parse precision: ${current}`);
  if (parsed === targetScale) return;
  const btn = targetScale > parsed ? page.getByTestId("grid-scale-plus") : page.getByTestId("grid-scale-minus");
  const step = targetScale > parsed ? 1 : -1;
  for (let scale = parsed; scale !== targetScale; scale += step) {
    await btn.click();
    const next = scale + step;
    const size = next === 0 ? 10 : next > 0 ? [12, 14, 16, 18, 20][next - 1] : [9, 8, 7, 6, 5][-next - 1];
    const nextLabel =
      next === 0 ? /Neutral \(10×10\)/ : next > 0 ? new RegExp(`\\+${next} \\(`) : new RegExp(`${next} \\(`);
    await expect(page.getByTestId("grid-scale-value")).toHaveText(nextLabel, { timeout: 15_000 });
    await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-grid-size", String(size), { timeout: 15_000 });
  }
}

function attachNetworkAudit(page: Page, failures: string[]) {
  page.on("response", (res) => {
    const url = res.url();
    if (!url.includes("/api/spatial-map/") && !url.includes("/characters")) return;
    if (res.status() >= 400) failures.push(`${res.status()} ${url}`);
  });
}

test.describe.serial("@critical Spatial Map Cartesian Grid + Entity Blocking", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("A — Neutral Cartesian 10×10, no radial rings", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-A-${Date.now()}`);
    const observer = new AuditObserver(page, info);
    observer.attach();
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      const grid = page.getByTestId("spatial-map-grid");
      await expect(grid).toBeVisible();
      await expect(grid).toHaveAttribute("data-grid-kind", "cartesian");
      await expect(grid).toHaveAttribute("data-grid-size", "10");
      await expect(grid).toHaveAttribute("data-grid-detail", "0");
      await expect(page.getByTestId("grid-scale-value")).toHaveText("Neutral (10×10)");
      await expect(page.locator(".spatial-map__grid-ring")).toHaveCount(0);
      await expect(page.locator(".spatial-map__grid-spoke")).toHaveCount(0);

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "01-neutral-10x10.png") });
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, `A-neutral-${info.testId}.png`) });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("B — Placement Precision +5 20×20 and -5 5×5", async ({ page, request }, info) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-B-${Date.now()}`);
    const observer = new AuditObserver(page, info);
    observer.attach();
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      await setPrecision(page, 5);
      await expect(page.getByTestId("grid-scale-value")).toHaveText("+5 (20×20)");
      await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-grid-size", "20");
      await expect(page.getByTestId("grid-scale-plus")).toBeDisabled();
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "02-grid-plus5-20x20.png") });

      await setPrecision(page, 0);
      await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-grid-size", "10");

      await setPrecision(page, -5);
      await expect(page.getByTestId("grid-scale-value")).toHaveText("-5 (5×5)");
      await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-grid-size", "5");
      await expect(page.getByTestId("grid-scale-minus")).toBeDisabled();
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "03-grid-minus5-5x5.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("C — Character dropdown Add Place Move reload", async ({ page, request, context }, info) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-C-${Date.now()}`);
    const observer = new AuditObserver(page, info);
    observer.attach();
    const failures: string[] = [];
    attachNetworkAudit(page, failures);
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await createCharacter(request, project.id, "Korri");
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      const select = page.getByTestId("character-select-0");
      await expect(select).toBeVisible({ timeout: 20_000 });
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "04-character-dropdown.png") });
      await expect(select.locator("option", { hasText: "Korri" })).toHaveCount(1);
      await select.selectOption({ label: "Korri" });
      await page.getByTestId("character-add-0").click();
      await expect(page.getByTestId("spatial-map-slot-character-0")).toContainText("Korri", { timeout: 15_000 });
      await expect(page.locator("input[aria-label='Character name']")).toHaveCount(0);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "05-korri-assigned.png") });

      await page.getByTestId("character-place-0").click();
      await expect(page.getByTestId("placement-mode-banner")).toContainText("Placing: Korri");
      await clickGridCell(page, 4, 4);
      const marker = page.locator('[data-testid^="placement-marker-"]').first();
      await expect(marker).toBeVisible();
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "06-korri-placed-grid-cell.png") });

      const before = await marker.boundingBox();
      await page.getByTestId("character-move-0").click();
      await expect(page.getByTestId("placement-mode-banner")).toContainText("Moving: Korri");
      await clickGridCell(page, 5, 4);
      await expect(page.getByTestId("placement-mode-banner")).toHaveCount(0);
      const after = await marker.boundingBox();
      const gridBox = await page.getByTestId("spatial-map-grid").boundingBox();
      expect(before && after && gridBox).toBeTruthy();
      const dist = Math.hypot((after!.x - before!.x), (after!.y - before!.y));
      const cell = gridBox!.width / 10;
      expect(dist).toBeGreaterThan(cell * 0.35);
      expect(dist).toBeLessThan(cell * 1.7);

      const page2 = await context.newPage();
      await page2.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page2, project.id);
      await openSpatialMapTab(page2);
      await expect(page2.getByTestId("spatial-map-slot-character-0")).toContainText("Korri", { timeout: 30_000 });
      await expect(page2.locator('[data-testid^="placement-marker-"]').first()).toBeVisible();
      await page2.close();
      expect(failures, failures.join("\n")).toEqual([]);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("D — Prop dropdown Add Place Move reload", async ({ page, request, context }, info) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-D-${Date.now()}`);
    const observer = new AuditObserver(page, info);
    observer.attach();
    const failures: string[] = [];
    attachNetworkAudit(page, failures);
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      const character = await createCharacter(request, project.id, "Korri");
      await createCharacterProp(request, project.id, character.id, "Lightsaber");
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      const select = page.getByTestId("prop-select-0");
      await expect(select.locator("option", { hasText: "Lightsaber" })).toHaveCount(1, { timeout: 20_000 });
      await select.selectOption({ label: "Lightsaber" });
      await page.getByTestId("prop-add-0").click();
      await expect(page.getByTestId("spatial-map-slot-prop-0")).toContainText("Lightsaber", { timeout: 15_000 });
      await page.getByTestId("prop-place-0").click();
      await clickGridCell(page, 3, 5);
      await expect(page.locator('[data-testid^="placement-marker-"]').first()).toBeVisible();
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "07-prop-placement.png") });
      await page.getByTestId("prop-move-0").click();
      await clickGridCell(page, 4, 5);

      const page2 = await context.newPage();
      await page2.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page2, project.id);
      await openSpatialMapTab(page2);
      await expect(page2.getByTestId("spatial-map-slot-prop-0")).toContainText("Lightsaber", { timeout: 30_000 });
      await expect(page2.locator('[data-testid^="placement-marker-"]').first()).toBeVisible();
      await page2.close();
      expect(failures, failures.join("\n")).toEqual([]);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("E — Camera C1 Place NE Wide Move reload", async ({ page, request, context }, info) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-E-${Date.now()}`);
    const observer = new AuditObserver(page, info);
    observer.attach();
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      await page.getByTestId("camera-add-0").click();
      await expect(page.getByTestId("camera-place-0")).toBeVisible();
      await page.getByTestId("camera-place-0").click();
      await expect(page.getByTestId("placement-mode-banner")).toContainText("Placing: C1");
      await clickGridCell(page, 6, 4);
      await expect(page.locator('[data-testid^="camera-marker-"]').first()).toBeVisible();
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "08-camera-c1.png") });

      await page.getByTestId("camera-rotate-right").click();
      await expect(page.getByTestId("camera-inspector-direction")).toHaveText("NE");
      await page.getByTestId("camera-fov-wide").click();
      await expect(page.getByTestId("camera-fov-wide")).toHaveClass(/is-active/);
      await expect(page.getByTestId("camera-fov-wide")).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByTestId("camera-fov-medium")).not.toHaveClass(/is-active/);
      await expect(page.getByTestId("camera-fov-medium")).toHaveAttribute("aria-pressed", "false");
      await expect(page.getByTestId("camera-inspector-direction")).toHaveText("NE");
      await expect(page.getByTestId("camera-slot-0")).toContainText(/NE/i);
      await expect(page.getByTestId("camera-slot-0")).toContainText(/wide/i);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "09-camera-ne-wide-fov.png") });

      await page.getByTestId("camera-move-0").click();
      await clickGridCell(page, 6, 5);

      const page2 = await context.newPage();
      await page2.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page2, project.id);
      await openSpatialMapTab(page2);
      await expect(page2.locator('[data-testid^="camera-marker-"]').first()).toBeVisible();
      await page2.locator('[data-testid^="camera-marker-"]').first().locator(".spatial-map__camera-hitbox").click();
      await expect(page2.getByTestId("camera-inspector-direction")).toHaveText("NE");
      await expect(page2.getByTestId("camera-fov-wide")).toHaveClass(/is-active/);
      await page2.close();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("F — physical position stability across precision changes", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-F-${Date.now()}`);
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      const character = await createCharacter(request, project.id, "Korri");
      await createCharacterProp(request, project.id, character.id, "Lightsaber");
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      await page.getByTestId("character-select-0").selectOption({ label: "Korri" });
      await page.getByTestId("character-add-0").click();
      await page.getByTestId("character-place-0").click();
      await clickGridCell(page, 4, 3);

      await page.getByTestId("prop-select-0").selectOption({ label: "Lightsaber" });
      await page.getByTestId("prop-add-0").click();
      await page.getByTestId("prop-place-0").click();
      await clickGridCell(page, 3, 6);

      await page.getByTestId("camera-add-0").click();
      await page.getByTestId("camera-place-0").click();
      await clickGridCell(page, 6, 4);

      const char = page.locator('[data-kind="character"]').first();
      const prop = page.locator('[data-kind="prop"]').first();
      const cam = page.locator('[data-testid^="camera-marker-"]').first();
      const origin = async () => {
        const a = await char.boundingBox();
        const b = await prop.boundingBox();
        const c = await cam.boundingBox();
        return { a, b, c };
      };
      const start = await origin();
      await setPrecision(page, 5);
      await setPrecision(page, -5);
      await setPrecision(page, 0);
      const end = await origin();
      const gridBox = await page.getByTestId("spatial-map-grid").boundingBox();
      const limit = (gridBox?.width || 500) * 0.22;
      const jump = (x?: { x: number; y: number } | null, y?: { x: number; y: number } | null) =>
        x && y ? Math.hypot(x.x - y.x, x.y - y.y) : Number.POSITIVE_INFINITY;
      expect(jump(start.a, end.a)).toBeLessThan(limit);
      expect(jump(start.b, end.b)).toBeLessThan(limit);
      expect(jump(start.c, end.c)).toBeLessThan(limit);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("G — mixed production blocking screenshot", async ({ page, request }, info) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-G-${Date.now()}`);
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      const korri = await createCharacter(request, project.id, "Korri");
      await createCharacter(request, project.id, "Anadriya");
      await createCharacterProp(request, project.id, korri.id, "Lightsaber");
      await createCharacterProp(request, project.id, korri.id, "Coffee Cup");
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);

      await page.getByTestId("character-select-0").selectOption({ label: "Korri" });
      await page.getByTestId("character-add-0").click();
      await page.getByTestId("character-place-0").click();
      await clickGridCell(page, 4, 4);

      await page.getByTestId("character-select-1").selectOption({ label: "Anadriya" });
      await page.getByTestId("character-add-1").click();
      await page.getByTestId("character-place-1").click();
      await clickGridCell(page, 5, 6);

      await page.getByTestId("prop-select-0").selectOption({ label: "Lightsaber" });
      await page.getByTestId("prop-add-0").click();
      await page.getByTestId("prop-place-0").click();
      await clickGridCell(page, 3, 4);

      await page.getByTestId("prop-select-1").selectOption({ label: "Coffee Cup" });
      await page.getByTestId("prop-add-1").click();
      await page.getByTestId("prop-place-1").click();
      await clickGridCell(page, 6, 5);

      await page.getByTestId("camera-add-0").click();
      await page.getByTestId("camera-place-0").click();
      await clickGridCell(page, 2, 5);
      await page.getByTestId("camera-rotate-right").click();
      await page.getByTestId("camera-fov-wide").click();

      await page.getByTestId("camera-add-1").click();
      await page.getByTestId("camera-place-1").click();
      await clickGridCell(page, 7, 3);
      await page.getByTestId("camera-fov-narrow").click();

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "10-mixed-production-blocking.png") });
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, `G-mixed-${info.testId}.png`) });
      await expect(page.getByTestId("spatial-map-grid")).toHaveAttribute("data-grid-size", "10");
      await expect(page.locator('[data-testid^="placement-marker-"]')).toHaveCount(4);
      await expect(page.locator('[data-testid^="camera-marker-"]')).toHaveCount(2);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("atlas — replace modal search Select Cancel", async ({ page, request }) => {
    test.setTimeout(120_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-ATLAS-${Date.now()}`);
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      const asset = await uploadAtlasImage(request, project.id);
      await createSpatialMap(request, project.id, asset.id);
      await openCoDirectorFullScreen(page, project.id);
      await openSpatialMapTab(page);
      await expect(page.getByTestId("spatial-map-grid")).toBeVisible();
      await openAndCloseAtlasModal(page);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
