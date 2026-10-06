import { expect, test, type APIRequestContext } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_NAME = "Movement Segment Brand Ad Smoke";

async function findOrCreateProject(request: APIRequestContext): Promise<string> {
  const listed = await request.get(`${API}/api/projects`);
  if (listed.ok()) {
    const body = (await listed.json()) as { projects?: Array<{ id: string; name: string }> } | Array<{ id: string; name: string }>;
    const items = Array.isArray(body) ? body : body.projects || [];
    const hit = items.find((p) => p.name === PROJECT_NAME);
    if (hit?.id) return hit.id;
  }
  const created = await request.post(`${API}/api/projects`, { data: { name: PROJECT_NAME } });
  expect(created.ok()).toBeTruthy();
  const payload = (await created.json()) as { id: string };
  return payload.id;
}

test.describe("Fresh Brand Ad Movement Segment smoke", () => {
  test("hallway map can hold M1-M3 without falling back to M1", async ({ request, page }) => {
    test.setTimeout(180_000);
    const projectId = await findOrCreateProject(request);
    const maps = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps`);
    expect(maps.ok()).toBeTruthy();
    let docs = ((await maps.json()) as { documents?: Array<{ id: string; backgroundAssetId?: string }> }).documents || [];
    if (!docs.length) {
      const created = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps`, {
        data: {
          title: "Hallway",
          sceneDescription: "A bright office hallway for a brand-ad walk from the counter to the table.",
        },
      });
      expect(created.ok(), await created.text()).toBeTruthy();
      docs = [((await created.json()) as { document: { id: string } }).document];
    }
    const mapId = docs[0].id;
    const current = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`);
    expect(current.ok()).toBeTruthy();
    let document = ((await current.json()) as { document: { movementSegments?: Array<{ id: string; segmentNumber: number }> } }).document;
    const existing = document.movementSegments || [];
    while (existing.filter((s) => s.segmentNumber > 1).length < 2 && existing.length < 5) {
      const add = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/movements`, {
        data: {
          beatName: existing.length === 1 ? "Leaves Counter" : "Reaches Table",
          userDirection: existing.length === 1 ? "She walks from the counter toward the table." : "She arrives at the table.",
        },
      });
      expect(add.ok(), await add.text()).toBeTruthy();
      document = ((await add.json()) as { document: { movementSegments?: Array<{ id: string; segmentNumber: number }> } }).document;
      existing.splice(0, existing.length, ...(document.movementSegments || []));
    }
    const segments = document.movementSegments || [];
    const numbers = segments.map((s) => s.segmentNumber).sort();
    expect(numbers).toEqual(expect.arrayContaining([1, 2, 3]));
    const m1 = segments.find((s) => s.segmentNumber === 1);
    const m2 = segments.find((s) => s.segmentNumber === 2);
    expect(m1?.id).toBeTruthy();
    expect(m2?.id).not.toBe(m1?.id);

    const missing = await request.post(
      `${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/movements/missing-id/activate`,
    );
    expect(missing.status()).toBe(404);
    const detail = (await missing.json()) as { detail?: { code?: string } };
    expect(detail.detail?.code || "").not.toBe("MOVEMENT_CANNOT_DELETE");
    expect(detail.detail?.code || "").toMatch(/MOVEMENT_SEGMENT_NOT_FOUND|NOT_FOUND/i);

    const deleteM1 = await request.delete(
      `${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/movements/${m1!.id}`,
    );
    expect(deleteM1.status()).toBe(409);

    const arrows = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/movement-arrows`);
    expect(arrows.ok()).toBeTruthy();

    await page.goto(`/project/${projectId}?workspace=spatial`, { waitUntil: "domcontentloaded", timeout: 60000 });
    const accordion = page.locator("[data-testid=movement-segments]");
    if (await accordion.isVisible({ timeout: 15000 }).catch(() => false)) {
      await expect(page.locator("[data-testid=movement-row-M1]")).toBeVisible();
      await expect(page.locator("[data-testid=movement-row-M2]")).toBeVisible();
      await expect(page.locator("[data-testid=movement-row-M3]")).toBeVisible();
      await expect(page.locator("[data-testid=movement-add]")).toBeVisible();
      await expect(page.locator("[data-testid=movement-remove-M1]")).toHaveCount(0);
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.locator("[data-testid=movement-row-M2]")).toBeVisible();
    }

    const qwen = await request.get(`${API}/api/image-product/families`);
    expect(qwen.ok()).toBeTruthy();
    const families = ((await qwen.json()) as { families?: Array<{ family?: string; executable?: boolean; status?: string }> }).families || [];
    const qwen2512 = families.find((f) => f.family === "qwen2512");
    expect(qwen2512?.executable).toBeTruthy();
  });
});
