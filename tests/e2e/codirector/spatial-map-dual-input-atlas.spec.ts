/**
 * Spatial Map dual-input + Co-Director Atlas — SenseNova Lab only.
 * Does not spawn projects. Does not mutate Korri / Jacob.
 */
import { deflateSync } from "node:zlib";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const CORRIDOR_TAG = "codirector_image_generate_d5d616be";
const LIVE_PHRASE =
  "Take codirector_image_generate_d5d616be in library and use that as a reference to create an atlas (top down shot) for the Spatial map.";

test.setTimeout(20 * 60 * 1000);

function realCrc32(buf: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of buf) {
    crc ^= byte;
    for (let i = 0; i < 8; i += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: Buffer): Buffer {
  const header = Buffer.alloc(8);
  header.writeUInt32BE(data.length, 0);
  header.write(type, 4, 4, "ascii");
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(realCrc32(Buffer.concat([header.subarray(4, 8), data])), 0);
  return Buffer.concat([header, data, crc]);
}

function rgbPng(width: number, height: number, pixel: (x: number, y: number) => [number, number, number]): Buffer {
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * (width * 3 + 1);
    raw[row] = 0;
    for (let x = 0; x < width; x += 1) {
      const [r, g, b] = pixel(x, y);
      const i = row + 1 + x * 3;
      raw[i] = r;
      raw[i + 1] = g;
      raw[i + 2] = b;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

function floorplanPng(): Buffer {
  return rgbPng(128, 128, (x, y) => {
    if (x % 16 < 2 || y % 16 < 2) return [40, 40, 40];
    if (x > 40 && x < 88 && y > 40 && y < 88) return [90, 90, 110];
    return [210, 210, 210];
  });
}

function perspectivePng(): Buffer {
  return rgbPng(192, 108, (x, y) => {
    const t = Math.min(255, Math.round((x * 180) / 191 + (y * 40) / 107));
    return [t, Math.min(255, t + 20), Math.max(0, t - 10)];
  });
}

async function listAssets(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/library`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (Array.isArray(body) ? body : body.items || body.assets || []) as Array<{
    id: string;
    tag?: string;
    filename?: string;
  }>;
}

async function findCorridor(request: APIRequestContext) {
  const assets = await listAssets(request);
  return (
    assets.find((a) => String(a.tag || "") === CORRIDOR_TAG) ||
    assets.find((a) => String(a.tag || "").includes("codirector_image_generate")) ||
    assets.find((a) => /corridor/i.test(String(a.tag || a.filename || "")))
  );
}

type AtlasExecution = {
  execution_id?: string;
  capability?: string;
  status?: string;
  created_at?: string;
  result_asset_ids?: string[];
  child_jobs?: Array<{ metadata?: Record<string, unknown> }>;
};

async function latestMap(request: APIRequestContext) {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const docs = ((await res.json()).documents || []) as Array<{
    id: string;
    backgroundAssetId?: string | null;
    widthMeters?: number;
    depthMeters?: number;
    notes?: string;
    updatedAt?: string;
  }>;
  return docs[0] || null;
}

async function listAtlasExecutions(request: APIRequestContext): Promise<AtlasExecution[]> {
  const res = await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/executions`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const executions = (body.executions || []) as AtlasExecution[];
  return executions.filter((exec) => exec.capability === "atlas.generate");
}

async function clearAtlas(request: APIRequestContext) {
  const map = await latestMap(request);
  if (!map?.id) return;
  const res = await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${map.id}`, {
    data: { backgroundAssetId: null },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const cleared = await latestMap(request);
  expect(cleared?.backgroundAssetId || null, "clearAtlas must remove the prior Atlas").toBeFalsy();
}

async function waitMs(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForNewAtlasExecution(
  request: APIRequestContext,
  knownIds: Set<string>,
  timeoutMs = 15 * 60 * 1000,
): Promise<AtlasExecution> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const listed = await listAtlasExecutions(request);
    const found = listed.find((item) => item.execution_id && !knownIds.has(item.execution_id));
    if (found) return found;
    await waitMs(2000);
  }
  throw new Error("Option 1 Library did not start a new atlas.generate execution");
}

async function waitForExecutionTerminal(
  request: APIRequestContext,
  executionId: string,
  timeoutMs = 15 * 60 * 1000,
): Promise<AtlasExecution> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/executions/${executionId}`);
    if (res.ok()) {
      const exec = (await res.json()) as AtlasExecution;
      if (["completed", "failed", "cancelled"].includes(String(exec.status || ""))) return exec;
    }
    await waitMs(2000);
  }
  throw new Error(`atlas.generate ${executionId} did not reach a terminal status`);
}

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) return;
    const skip = region.getByRole("button", { name: /Skip for now/i }).first();
    if (await skip.isVisible().catch(() => false)) {
      await skip.click({ force: true }).catch(() => undefined);
    }
    await page.waitForTimeout(400);
  }
}

async function openSpatialMap(page: Page) {
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

async function waitForGrid(page: Page) {
  const close = page.getByTestId("agent-work-close");
  if (await close.isVisible().catch(() => false)) {
    await close.click({ force: true }).catch(() => undefined);
  }
  await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 15 * 60 * 1000 });
  await expect(page.getByTestId("spatial-map-grid")).toBeVisible({ timeout: 30_000 });
}

async function streamChat(request: APIRequestContext, message: string) {
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages: [{ role: "user", content: message }],
      project_id: PROJECT_ID,
      mode: "chat",
    },
    timeout: 180_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const events: Record<string, unknown>[] = [];
  for (const line of (await res.body()).toString("utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice(5).trim();
    if (!payload) continue;
    try {
      events.push(JSON.parse(payload));
    } catch {
      /* ignore */
    }
  }
  return events;
}

test.describe("SenseNova Spatial Map dual-input Atlas", () => {
  test("chat Library phrasing routes to atlas.generate, never Assign_reference", async ({ request }) => {
    const events = await streamChat(request, LIVE_PHRASE);
    const blob = JSON.stringify(events);
    expect(blob).not.toMatch(/assign_reference/i);
    expect(blob).toMatch(/atlas\.generate/);
    expect(blob).not.toMatch(/How should this place look and sound/i);
    const execId = events
      .map((evt) => (evt.execution as { execution_id?: string } | undefined)?.execution_id)
      .find(Boolean);
    if (execId) {
      await request.post(`${API}/api/codirector/projects/${PROJECT_ID}/executions/${execId}/cancel`).catch(() => undefined);
    }
  });

  test("empty state shows Option 1 transform and Option 2 existing Atlas", async ({ page, request }) => {
    await clearAtlas(request);
    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMap(page);
    await expect(page.getByTestId("spatial-map-start-chooser")).toBeVisible();
    await expect(page.getByTestId("spatial-map-start-location")).toContainText("Create Spatial Map from a Location Image");
    await expect(page.getByTestId("spatial-map-start-location")).toContainText("analyze the architecture");
    await expect(page.getByTestId("spatial-map-start-location")).toContainText("1-meter structural map");
    await expect(page.getByTestId("spatial-map-start-atlas")).toContainText("Use an Existing Spatial Map");
    await expect(page.getByTestId("spatial-map-grid")).toHaveCount(0);
    await page.getByTestId("atlas-image-engine-advanced").locator("summary").click();
    await expect(page.getByTestId("atlas-look-controls")).toBeVisible();
    const style = page.getByTestId("atlas-look-style");
    await expect(style).toBeVisible();
    if (await style.isEnabled()) {
      await style.selectOption("architectural");
      await expect(style).toHaveValue("architectural");
      await page.getByTestId("atlas-look-detail").selectOption("high");
      await expect(page.getByTestId("atlas-look-detail")).toHaveValue("high");
      await page.getByTestId("atlas-look-lighting").selectOption("bright_planning");
      await expect(page.getByTestId("atlas-look-lighting")).toHaveValue("bright_planning");
    } else {
      await expect(style).toBeDisabled();
    }
  });

  test("Advanced Look persists on the open map via API and reload", async ({ page, request }) => {
    const maps = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
    expect(maps.ok(), await maps.text()).toBeTruthy();
    const docs = ((await maps.json()).documents || []) as Array<{ id: string; atlasLook?: Record<string, unknown> }>;
    const map = docs[0];
    expect(map?.id, "SenseNova must already have a Spatial Map").toBeTruthy();
    const look = {
      style: "architectural",
      detail: "balanced",
      sourceAppearance: "balanced",
      presentation: "roofless",
      lighting: "bright_planning",
      showGrid: false,
    };
    const patch = await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${map.id}`, {
      data: { atlasLook: look },
    });
    expect(patch.ok(), await patch.text()).toBeTruthy();
    const saved = (await patch.json()).document || (await patch.json());
    expect(saved.atlasLook?.style).toBe("architectural");
    expect(saved.atlasLook?.lighting).toBe("bright_planning");
    const again = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${map.id}`);
    const againDoc = (await again.json()).document || {};
    expect(againDoc.atlasLook?.style).toBe("architectural");
    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMap(page);
    await page.getByTestId("atlas-image-engine-advanced").locator("summary").click();
    await expect(page.getByTestId("atlas-look-style")).toHaveValue("architectural");
    await expect(page.getByTestId("atlas-look-lighting")).toHaveValue("bright_planning");
  });

  test("Option 1 Library — corridor master generates Atlas and activates grid", async ({ page, request }) => {
    const corridor = await findCorridor(request);
    expect(corridor?.id, "SenseNova corridor Library asset").toBeTruthy();
    const priorMap = await latestMap(request);
    const priorBackground = priorMap?.backgroundAssetId || null;
    const knownExecIds = new Set((await listAtlasExecutions(request)).map((exec) => String(exec.execution_id || "")));
    await clearAtlas(request);
    const classify = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/atlas-source/classify`, {
      data: { assetId: corridor!.id, intendedRoute: "transform" },
    });
    expect(classify.ok(), await classify.text()).toBeTruthy();
    const classification = await classify.json();
    expect(classification.pixelsRead).toBeTruthy();

    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMap(page);
    await page.getByTestId("spatial-map-location-library").click();
    const search = page.getByTestId("environment-picker-search");
    if (await search.isVisible().catch(() => false)) {
      await search.fill(String(corridor!.tag || CORRIDOR_TAG));
    }
    const card = page.getByTestId(`environment-asset-${corridor!.id}`);
    await expect(card).toBeVisible({ timeout: 20_000 });
    await card.click();
    await page.getByTestId("environment-picker-confirm").click();
    if (classification.action === "generate") {
      const exec = await waitForNewAtlasExecution(request, knownExecIds);
      const finished = await waitForExecutionTerminal(request, String(exec.execution_id));
      expect(finished.status, `new atlas.generate ended ${finished.status}`).toBe("completed");
      const atlasId = finished.result_asset_ids?.[0] || "";
      expect(atlasId, "new atlas.generate must produce a candidate asset").toBeTruthy();
      const gateRes = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/atlas-candidate/validate`, {
        data: {
          atlasAssetId: atlasId,
          sourceAssetId: corridor!.id,
          executionId: exec.execution_id,
        },
      });
      expect(gateRes.ok(), await gateRes.text()).toBeTruthy();
      const gate = await gateRes.json();
      const map = await latestMap(request);
      expect(map?.backgroundAssetId || null).not.toBe(priorBackground);
      expect(map?.backgroundAssetId || null).not.toBe(corridor!.id);
      expect(gate.ok, gate.reason || gate.failCode || "visual gate must PASS for compiler E2E").toBeTruthy();
      expect(map?.backgroundAssetId).toBe(atlasId);
      if (gate.acceptedMetrics?.widthMeters) {
        expect(map?.widthMeters).toBe(gate.acceptedMetrics.widthMeters);
      }
    }
    await waitForGrid(page);
  });

  test("Option 1 Upload — wide environment starts transform, not silent assign of source", async ({ page, request }) => {
    const priorBackground = (await latestMap(request))?.backgroundAssetId || null;
    await clearAtlas(request);
    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMap(page);
    const chooser = page.waitForEvent("filechooser");
    await page.getByTestId("spatial-map-location-upload").click();
    await (await chooser).setFiles({
      name: "location-master.png",
      mimeType: "image/png",
      buffer: perspectivePng(),
    });
    await expect
      .poll(async () => {
        const map = await latestMap(request);
        return Boolean(map?.backgroundAssetId && map.backgroundAssetId !== priorBackground);
      }, { timeout: 15 * 60 * 1000 })
      .toBeTruthy();
    await waitForGrid(page);
  });

  test("Option 2 Library — existing Atlas assigns without generation", async ({ page, request }) => {
    const uploaded = await request.post(`${API}/api/projects/${PROJECT_ID}/assets`, {
      multipart: {
        file: { name: "existing-atlas.png", mimeType: "image/png", buffer: floorplanPng() },
        tag: "atlas_shot",
        kind: "image",
      },
    });
    expect(uploaded.ok(), await uploaded.text()).toBeTruthy();
    const asset = await uploaded.json();
    await clearAtlas(request);

    let generatePosted = false;
    await page.route("**/api/codirector/projects/**/executions", async (route) => {
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON() as { capability?: string };
        if (body?.capability === "atlas.generate") generatePosted = true;
      }
      await route.continue();
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMap(page);
    await page.getByTestId("spatial-map-atlas-library").click();
    const search = page.getByTestId("environment-picker-search");
    if (await search.isVisible().catch(() => false)) {
      await search.fill("existing-atlas");
    }
    const card = page.getByTestId(`environment-asset-${asset.id}`);
    await expect(card).toBeVisible({ timeout: 20_000 });
    await card.click();
    await page.getByTestId("environment-picker-confirm").click();
    await waitForGrid(page);
    const map = await latestMap(request);
    expect(map?.backgroundAssetId).toBe(asset.id);
    expect(generatePosted).toBeFalsy();
  });

  test("Option 2 Upload — valid Atlas assigns without regeneration", async ({ page, request }) => {
    await clearAtlas(request);
    let generatePosted = false;
    await page.route("**/api/codirector/projects/**/executions", async (route) => {
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON() as { capability?: string };
        if (body?.capability === "atlas.generate") generatePosted = true;
      }
      await route.continue();
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMap(page);
    const chooser = page.waitForEvent("filechooser");
    await page.getByTestId("spatial-map-atlas-upload").click();
    await (await chooser).setFiles({
      name: "upload-atlas.png",
      mimeType: "image/png",
      buffer: floorplanPng(),
    });
    await waitForGrid(page);
    expect(generatePosted).toBeFalsy();
  });
});
