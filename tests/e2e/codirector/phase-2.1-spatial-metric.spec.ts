/**
 * Phase 2.1 Spatial Metric — Schnick Coffee only.
 * 12 m martial-arts spacing, camera lock, persist, 1 m UI, no new project.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const MAP_TITLE = "Martial Arts Metric Cert";

async function listChars(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/characters`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const items = (body.characters || body.items || body || []) as Array<{ id: string; name?: string }>;
  return Array.isArray(items) ? items : [];
}

async function findOrCreateMap(request: APIRequestContext) {
  const listed = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(listed.ok(), await listed.text()).toBeTruthy();
  const docs = ((await listed.json()).documents || []) as Array<{ id: string; title?: string }>;
  const existing = docs.find((d) => d.title === MAP_TITLE);
  if (existing) return existing.id;
  const created = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`, {
    data: { title: MAP_TITLE, widthMeters: 20, depthMeters: 20, metersPerCell: 1 },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  return ((await created.json()).document as { id: string }).id;
}

test.describe("Phase 2.1 Spatial Metric 8760→8758", () => {
  test.skip(!BETA_TARGET, "Phase 2.1 certifies 8760→8758 only");
  test.skip(!String(API).includes("8758"), `API must be :8758, got ${API}`);

  let mapId = "";
  let redId = "";
  let blueId = "";
  let cameraId = "";

  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
    mapId = await findOrCreateMap(request);
    await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`, {
      data: { widthMeters: 20, depthMeters: 20, metersPerCell: 1 },
    });
    const chars = await listChars(request);
    expect(chars.length, "Schnick must already have characters").toBeGreaterThan(0);
    const a = chars[0];
    const b = chars[1] || chars[0];
    const mapRes = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
    const map = (await mapRes.json()).document as {
      characters?: Array<{ id: string; characterId?: string }>;
      cameras?: Array<{ id: string }>;
    };
    const placed = map.characters || [];
    if (placed.length < 2) {
      const red = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/characters`, {
        data: { characterId: a.id, label: "Red", x: -6, y: 0, z: 0 },
      });
      expect(red.ok(), await red.text()).toBeTruthy();
      const blue = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/characters`, {
        data: { characterId: b.id, label: "Blue", x: 6, y: 0, z: 0 },
      });
      expect(blue.ok(), await blue.text()).toBeTruthy();
    } else {
      await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/characters/${placed[0].id}`, {
        data: { x: -6, y: 0, z: 0 },
      });
      await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/characters/${placed[1].id}`, {
        data: { x: 6, y: 0, z: 0 },
      });
    }
    const afterPlace = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
    const placedDoc = (await afterPlace.json()).document;
    redId = placedDoc.characters[0].id;
    blueId = placedDoc.characters[1].id;
    if (!(placedDoc.cameras || []).length) {
      const cam = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/cameras`, {
        data: { label: "Metric Hero", x: 0, y: 1.6, z: 8, heightMeters: 1.6 },
      });
      expect(cam.ok(), await cam.text()).toBeTruthy();
    }
    const withCam = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
    cameraId = ((await withCam.json()).document.cameras[0] as { id: string }).id;
  });

  test("A 20×20 map, 1 m cells, no zones, 12 m fighters", async ({ request }) => {
    const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
    expect(res.ok(), await res.text()).toBeTruthy();
    const doc = (await res.json()).document;
    expect(doc.zones).toBeUndefined();
    expect(doc.metricSchema).toBe("spatial-metric-v1");
    expect(doc.metersPerCell).toBe(1);
    expect(doc.widthMeters).toBe(20);
    expect(doc.depthMeters).toBe(20);
    const a = doc.characters.find((c: { id: string }) => c.id === redId);
    const b = doc.characters.find((c: { id: string }) => c.id === blueId);
    expect(a.positionMeters.x).toBeCloseTo(-6, 3);
    expect(b.positionMeters.x).toBeCloseTo(6, 3);
    const dx = b.positionMeters.x - a.positionMeters.x;
    const dz = b.positionMeters.z - a.positionMeters.z;
    expect(Math.hypot(dx, dz)).toBeCloseTo(12, 3);
  });

  test("B camera look/raise/orbit does not move characters", async ({ request }) => {
    const before = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
    const beforeDoc = (await before.json()).document;
    const beforeChars = JSON.stringify(beforeDoc.characters.map((c: { id: string; x: number; z: number }) => [c.id, c.x, c.z]));
    const moved = await request.patch(
      `${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}/cameras/${cameraId}`,
      { data: { lookAtId: redId, raiseMeters: 2, orbitDegrees: 40 } },
    );
    expect(moved.ok(), await moved.text()).toBeTruthy();
    const after = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
    const afterDoc = (await after.json()).document;
    const afterChars = JSON.stringify(afterDoc.characters.map((c: { id: string; x: number; z: number }) => [c.id, c.x, c.z]));
    expect(afterChars).toBe(beforeChars);
    const cam = afterDoc.cameras.find((c: { id: string }) => c.id === cameraId);
    expect(cam.heightMeters).toBeGreaterThan(1.6);
    expect(cam.x !== 0 || cam.z !== 8).toBeTruthy();
  });

  test("C persist after reload and project isolation", async ({ request, page }) => {
    await page.goto(`/project/${PROJECT_ID}?workspace=spatial`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await expect(page.locator("[data-testid=spatial-map-panel]")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator("[data-testid=spatial-metric-scale]")).toHaveText("1 square = 1 meter");
    await page.reload({ waitUntil: "domcontentloaded" });
    const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`);
    const doc = (await res.json()).document;
    expect(doc.id).toBe(mapId);
    expect(doc.projectId).toBe(PROJECT_ID);
    const dx = doc.characters[1].positionMeters.x - doc.characters[0].positionMeters.x;
    const dz = doc.characters[1].positionMeters.z - doc.characters[0].positionMeters.z;
    expect(Math.hypot(dx, dz)).toBeCloseTo(12, 3);
    const other = await request.get(`${API}/api/spatial-map/projects/00000000-0000-0000-0000-000000000000/maps/${mapId}`);
    expect(other.status()).toBeGreaterThanOrEqual(400);
  });
});
