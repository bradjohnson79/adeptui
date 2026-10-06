/**
 * Spatial Map native aspect — 4:3 and 16:9 contain-fit on the named Korri project.
 * Reuses or creates two maps on that project only. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";

test.setTimeout(6 * 60 * 1000);

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
};

const CASES = [
  { title: "Native Aspect 4:3", width: 800, height: 600, aspect: 4 / 3, tag: "native-aspect-4x3" },
  { title: "Native Aspect 16:9", width: 1280, height: 720, aspect: 16 / 9, tag: "native-aspect-16x9" },
] as const;

function pngBytes(width: number, height: number, r: number, g: number, b: number): Buffer {
  // Minimal uncompressed PNG via Playwright is awkward; use a data URL decode of a
  // 1×1 PNG scaled is wrong. Generate a real PNG with zlib through a tiny encoder.
  const zlib = require("zlib") as typeof import("zlib");
  const crcTable = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[n] = c;
    }
    return table;
  })();
  const crc32 = (buf: Buffer) => {
    let crc = 0xffffffff;
    for (let i = 0; i < buf.length; i += 1) crc = crcTable[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const typeBuf = Buffer.from(type, "ascii");
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])));
    return Buffer.concat([len, typeBuf, data, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * (width * 3 + 1);
    raw[row] = 0;
    for (let x = 0; x < width; x += 1) {
      const i = row + 1 + x * 3;
      raw[i] = r;
      raw[i + 1] = g;
      raw[i + 2] = b;
    }
  }
  const idat = zlib.deflateSync(raw);
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", idat),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function listMaps(request: APIRequestContext): Promise<MapDoc[]> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), "list Spatial Maps").toBeTruthy();
  const body = await res.json();
  return (body.documents || []) as MapDoc[];
}

async function ensureAspectMap(
  request: APIRequestContext,
  spec: (typeof CASES)[number],
): Promise<MapDoc> {
  const existing = (await listMaps(request)).find((m) => m.title === spec.title && m.backgroundAssetId);
  if (existing) return existing;

  const bytes = pngBytes(spec.width, spec.height, spec.title.includes("16") ? 40 : 220, 80, spec.title.includes("16") ? 220 : 40);
  const upload = await request.post(`${API}/api/projects/${PROJECT_ID}/assets`, {
    multipart: {
      file: { name: `${spec.tag}.png`, mimeType: "image/png", buffer: bytes },
      tag: spec.tag,
      kind: "image",
    },
  });
  expect(upload.ok(), `upload ${spec.tag}`).toBeTruthy();
  const asset = await upload.json();
  const created = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`, {
    data: {
      title: spec.title,
      backgroundAssetId: asset.id,
      geometrySource: "supplied",
      sceneDescription: `${spec.title} is a calibration plate for Spatial Map native aspect. Keep the full source picture visible under the fixed 1-meter grid.`,
    },
  });
  expect(created.ok(), `create ${spec.title}`).toBeTruthy();
  const body = await created.json();
  return (body.document || body) as MapDoc;
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
  if ((await select.count()) && (await select.isVisible().catch(() => false))) {
    await select.selectOption(mapId);
    await expect(select).toHaveValue(mapId, { timeout: 15_000 });
  }
  if (title) {
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
    await expect(heading).toBeVisible({ timeout: 15_000 });
  }
  await expect(page.getByTestId("spatial-map-grid")).toBeVisible({ timeout: 20_000 });
}

test.describe("Spatial Map native aspect", () => {
  for (const spec of CASES) {
    test(`${spec.title} displays contain-fit and persists`, async ({ page, request }) => {
      const map = await ensureAspectMap(request, spec);
      await openMap(page, map.id, spec.title);

      const atlas = page.getByTestId("spatial-map-atlas-layer");
      await expect(atlas).toHaveAttribute("data-fit", "contain", { timeout: 20_000 });
      await expect
        .poll(async () => Number(await atlas.getAttribute("data-aspect")), { timeout: 20_000 })
        .toBeCloseTo(spec.aspect, 2);

      const imgW = Number(await atlas.getAttribute("data-image-width"));
      const imgH = Number(await atlas.getAttribute("data-image-height"));
      expect(imgW).toBeGreaterThan(0);
      expect(imgH).toBeGreaterThan(0);
      expect(imgW / imgH).toBeCloseTo(spec.aspect, 2);
      expect(Math.abs(imgW - imgH)).toBeGreaterThan(8);

      const gridPath = await page.getByTestId("spatial-map-grid-lines").getAttribute("d");
      await page.getByTestId("background-alignment-resize").click();
      await page.getByTestId("background-alignment-scale").fill("130");
      await page.getByTestId("background-alignment-scale").blur();
      await expect(atlas).toHaveAttribute("data-scale", /1\.3/);
      expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(spec.aspect, 2);
      expect(await page.getByTestId("spatial-map-grid-lines").getAttribute("d")).toBe(gridPath);
      await page.getByTestId("background-alignment-resize").click();

      await page.getByTestId("background-alignment-hand").click();
      const grid = page.getByTestId("spatial-map-grid");
      const box = await grid.boundingBox();
      expect(box).toBeTruthy();
      await grid.dragTo(grid, {
        sourcePosition: { x: box!.width / 2, y: box!.height / 2 },
        targetPosition: { x: box!.width / 2 + 28, y: box!.height / 2 + 12 },
      });
      expect(Number(await atlas.getAttribute("data-scale"))).toBeCloseTo(1.3, 2);
      expect(Number(await atlas.getAttribute("data-aspect"))).toBeCloseTo(spec.aspect, 2);
      expect(Number(await atlas.getAttribute("data-offset-x"))).not.toBe(0);
      await page.getByTestId("background-alignment-hand").click();

      await page.getByTestId("spatial-map-save").click();
      await expect(page.getByTestId("spatial-map-save-state")).toContainText(/^Saved$/i, { timeout: 20_000 });

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
      await openMap(page, map.id, spec.title);
      await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-fit", "contain");
      await expect
        .poll(async () => Number(await page.getByTestId("spatial-map-atlas-layer").getAttribute("data-aspect")))
        .toBeCloseTo(spec.aspect, 2);
      await expect(page.getByTestId("spatial-map-atlas-layer")).toHaveAttribute("data-scale", /1\.3/);

      const live = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${map.id}`);
      const doc = ((await live.json()).document || {}) as MapDoc;
      expect(Number(doc.backgroundAlignment?.sourceWidth)).toBe(spec.width);
      expect(Number(doc.backgroundAlignment?.sourceHeight)).toBe(spec.height);
      expect(Number(doc.backgroundAlignment?.sourceAspectRatio)).toBeCloseTo(spec.aspect, 2);
      expect(Number(doc.backgroundAlignment?.scale)).toBeCloseTo(1.3, 2);
    });
  }
});
