/**
 * Revision B live closure — Playwright A–H.
 *
 * Certifies 8760 → 8758 only. Isolated 5174→8742 is not this topology.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);

async function uploadAtlas(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: { name: "atlas.png", mimeType: "image/png", buffer: TINY_PNG },
      tag: "atlas_shot",
      kind: "image",
    },
  });
  expect(res.ok(), `uploadAtlas failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { id: string };
}

async function createMap(request: APIRequestContext, projectId: string, backgroundAssetId: string) {
  const res = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps`, {
    data: { title: "Revision B Scene Review", backgroundAssetId },
  });
  expect(res.ok(), `createMap failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { document: { id: string } };
}

async function openSpatial(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=spatial`, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await expect(page.locator("[data-testid=spatial-map-panel]")).toBeVisible({ timeout: 60_000 });
}

async function readMap(request: APIRequestContext, projectId: string, mapId: string) {
  const res = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as { document: { characters?: unknown[]; props?: unknown[]; cameras?: unknown[]; zones?: unknown } };
}

test.describe("Revision B Creation Intelligence 8760→8758", () => {
  test.skip(!BETA_TARGET, "Revision B live closure certifies 8760→8758 only");
  test.skip(!String(API).includes("8758"), `API must be :8758, got ${API}`);

  let projectId = "";
  let mapId = "";
  let acceptedCameraId = "";

  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), await health.text()).toBeTruthy();
    const healthBody = await health.json();
    expect(healthBody.routeContract || []).toContain("perception.capability");
    const cap = await request.get(`${API}/api/perception/capability`);
    expect(cap.ok(), `8758 must expose /api/perception: ${await cap.text()}`).toBeTruthy();
    const project = await createTempProject(request, `Rev B Perception ${Date.now()}`);
    projectId = project.id;
    const atlas = await uploadAtlas(request, projectId);
    const created = await createMap(request, projectId, atlas.id);
    mapId = created.document.id;
  });

  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId).catch(() => undefined);
  });

  test("A Review drafts without writing slots", async ({ request, page }) => {
    const review = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/review`);
    expect(review.ok(), await review.text()).toBeTruthy();
    const body = await review.json();
    expect(body.draft.reviewLabel).toBe("CD Scene Review");
    expect(body.draft.mapId).toBe(mapId);
    const after = await readMap(request, projectId, mapId);
    expect(after.document.characters || []).toHaveLength(0);
    expect(after.document.props || []).toHaveLength(0);
    expect(after.document.cameras || []).toHaveLength(0);
    expect(after.document.zones).toBeUndefined();

    await openSpatial(page, projectId);
    await expect(page.locator("[data-testid=cd-scene-review]")).toBeVisible();
    await expect(page.getByText("Auto Map")).toHaveCount(0);
    await expect(page.locator(".spatial-map__slots")).toBeVisible();
    await page.locator("[data-testid=cd-scene-review-run]").click();
    await expect(page.locator("[data-testid=cd-scene-review-draft]")).toBeVisible({ timeout: 45_000 });
    const still = await readMap(request, projectId, mapId);
    expect(still.document.characters || []).toHaveLength(0);
    expect(still.document.cameras || []).toHaveLength(0);
  });

  test("B Accept writes place_* slots", async ({ request, page }) => {
    const review = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/review`);
    const body = await review.json();
    const camera = (body.draft.proposedFills || []).find((item: { kind: string }) => item.kind === "camera");
    expect(camera, "review must propose a camera").toBeTruthy();
    const accept = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/accept`, {
      data: { items: [{ fillId: camera.id }] },
    });
    expect(accept.ok(), await accept.text()).toBeTruthy();
    const accepted = await accept.json();
    expect(accepted.acceptedFillIds).toContain(camera.id);
    const document = await readMap(request, projectId, mapId);
    expect((document.document.cameras || []).length).toBeGreaterThan(0);
    acceptedCameraId = String((document.document.cameras || [])[0]?.id || "");
    expect(acceptedCameraId).toBeTruthy();

    await openSpatial(page, projectId);
    await expect(page.locator("[data-testid=camera-slot-0]")).toBeVisible();
  });

  test("C correction survives save and reload", async ({ request, page }) => {
    const review = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/review`);
    const body = await review.json();
    const fill = (body.draft.proposedFills || [])[0];
    expect(fill, "need a fill to correct").toBeTruthy();
    const key = `fill:${String(fill.label || fill.id).toLowerCase()}`;
    const corrected = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/corrections`, {
      data: { corrections: [{ factKey: key, action: "reject", value: {} }] },
    });
    expect(corrected.ok(), await corrected.text()).toBeTruthy();
    const again = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/review`);
    expect(again.ok(), await again.text()).toBeTruthy();
    const afterReview = await again.json();
    const corrections = afterReview.draft.userCorrections || [];
    expect(JSON.stringify(corrections).toLowerCase()).toContain(key.split(":")[1]);

    const persisted = await request.get(`${API}/api/perception/projects/${projectId}/maps/${mapId}/draft`);
    expect(persisted.ok(), await persisted.text()).toBeTruthy();
    const draft = await persisted.json();
    expect(JSON.stringify(draft.draft?.userCorrections || []).toLowerCase()).toContain(key.split(":")[1]);

    await openSpatial(page, projectId);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("[data-testid=spatial-map-panel]")).toBeVisible({ timeout: 60_000 });
    const reloaded = await request.get(`${API}/api/perception/projects/${projectId}/maps/${mapId}/draft`);
    const reloadedBody = await reloaded.json();
    expect(JSON.stringify(reloadedBody.draft?.userCorrections || []).toLowerCase()).toContain(key.split(":")[1]);
  });

  test("D geometry unavailable still allows the manual map", async ({ request, page }) => {
    const review = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/review`);
    const body = await review.json();
    expect(["unavailable", "available", "testing"]).toContain(body.draft.geometryStatus);
    await openSpatial(page, projectId);
    await page.locator("[data-testid=cd-scene-review-run]").click();
    await expect(page.locator("[data-testid=cd-scene-review-draft]")).toBeVisible({ timeout: 45_000 });
    if (body.draft.geometryStatus === "unavailable") {
      await expect(page.locator("[data-testid=cd-scene-review-geometry-unavailable]")).toBeVisible();
    }
    await expect(page.locator(".spatial-map__slots")).toBeVisible();
    await expect(page.getByText("Characters")).toBeVisible();
    await expect(page.getByText("Props")).toBeVisible();
    await expect(page.getByText("Cameras")).toBeVisible();
  });

  test("E Smart Select does not fake a mask", async ({ request, page }) => {
    const res = await request.post(`${API}/api/perception/projects/${projectId}/auto-mask`, {
      data: { mapId, label: "lamp" },
      timeout: 20_000,
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    if (body.ok) {
      expect(body.maskAssetId).toBeTruthy();
    } else {
      expect(body.maskAssetId).toBe("");
      expect(String(body.message).toLowerCase()).toMatch(/paint|not installed|essentials pack|gpu|memory/);
    }

    await page.goto(`/project/${projectId}?workspace=scenecreator`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    const smart = page.locator("[data-testid=scene-creator-inpaint-smart-select]");
    if (await smart.isVisible().catch(() => false)) {
      await smart.click();
      await expect(page.locator("[data-testid=scene-creator-smart-select-message]")).toContainText(
        /paint|not installed|essentials pack/i,
        { timeout: 20_000 },
      );
    }
  });

  test("F forced review failure stops the spinner", async ({ page }) => {
    await openSpatial(page, projectId);
    await page.route("**/api/perception/**/review", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: { message: "RuntimeError: worker crashed" } }),
      });
    });
    await page.locator("[data-testid=cd-scene-review-run]").click();
    await expect(page.locator("[data-testid=cd-scene-review-message]")).toBeVisible({ timeout: 20_000 });
    await expect(page.locator("[data-testid=cd-scene-review-run]")).toHaveText("Review this scene");
    await expect(page.locator("[data-testid=cd-scene-review-message]")).toContainText("Scene review couldn't start.");
    await expect(page.locator("[data-testid=cd-scene-review-message]")).not.toContainText("RuntimeError");
    await expect(page.locator("[data-testid=cd-scene-review-retry]")).toBeVisible();
    await page.unroute("**/api/perception/**/review");
  });

  test("G duplicate Review while in flight does not double-submit", async ({ page }) => {
    let count = 0;
    await openSpatial(page, projectId);
    await page.route("**/api/perception/**/review", async (route) => {
      count += 1;
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await route.continue();
    });
    const run = page.locator("[data-testid=cd-scene-review-run]");
    await run.click();
    await run.click({ force: true }).catch(() => undefined);
    await expect(run).toHaveText("Review this scene", { timeout: 45_000 });
    expect(count).toBe(1);
    await page.unroute("**/api/perception/**/review");
  });

  test("H browser 8760 persists through 8758 after reload", async ({ request, page }) => {
    expect(API).toContain("8758");

    const review = async () => {
      const res = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/review`);
      expect(res.ok(), await res.text()).toBeTruthy();
      return res.json() as Promise<{ draft: { proposedFills?: Array<{ id: string; kind: string }> } }>;
    };
    const acceptCamera = async (fillId: string) => {
      const res = await request.post(`${API}/api/perception/projects/${projectId}/maps/${mapId}/accept`, {
        data: { items: [{ fillId }] },
      });
      expect(res.ok(), await res.text()).toBeTruthy();
      return res.json() as Promise<{ acceptedFillIds?: string[]; failures?: Array<{ code?: string }> }>;
    };

    let before = await readMap(request, projectId, mapId);
    if ((before.document.cameras || []).length === 0) {
      const body = await review();
      const camera = (body.draft.proposedFills || []).find((item) => item.kind === "camera");
      expect(camera, "review must propose a camera so H can seed persistence").toBeTruthy();
      const accepted = await acceptCamera(camera!.id);
      expect(accepted.acceptedFillIds || []).toContain(camera!.id);
      before = await readMap(request, projectId, mapId);
    }
    expect((before.document.cameras || []).length).toBeGreaterThan(0);
    const cameraId = String((before.document.cameras || [])[0]?.id || "");
    expect(cameraId).toBeTruthy();
    if (acceptedCameraId) {
      expect((before.document.cameras || []).some((item: { id?: string }) => item.id === acceptedCameraId)).toBeTruthy();
    }

    const reviewed = await review();
    const midReview = await readMap(request, projectId, mapId);
    expect((midReview.document.cameras || []).some((item: { id?: string }) => item.id === cameraId)).toBeTruthy();

    const cameraFill = (reviewed.draft.proposedFills || []).find((item) => item.kind === "camera");
    if (cameraFill) {
      const accepted = await acceptCamera(cameraFill.id);
      const occupied = (accepted.failures || []).some((item) => item.code === "SLOT_OCCUPIED");
      if (!occupied) {
        expect(accepted.acceptedFillIds || []).toContain(cameraFill.id);
      }
    }
    await request.post(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/save`).catch(() => undefined);

    const midAccept = await readMap(request, projectId, mapId);
    expect((midAccept.document.cameras || []).length).toBeGreaterThan(0);
    expect((midAccept.document.cameras || []).some((item: { id?: string }) => item.id === cameraId)).toBeTruthy();

    await openSpatial(page, projectId);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("[data-testid=spatial-map-panel]")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator("[data-testid=cd-scene-review]")).toBeVisible();
    await expect(page.locator("[data-testid=camera-slot-0]")).toBeVisible();

    const again = await readMap(request, projectId, mapId);
    expect((again.document.cameras || []).length).toBeGreaterThan(0);
    expect((again.document.cameras || []).some((item: { id?: string }) => item.id === cameraId)).toBeTruthy();
    const draft = await request.get(`${API}/api/perception/projects/${projectId}/maps/${mapId}/draft`);
    expect(draft.ok()).toBeTruthy();
  });

  test("NL shot parse keeps spatial language", async ({ request }) => {
    const text =
      "Put Korri behind the service counter beside the espresso machine while Anadriya stands on the customer side facing her.";
    const res = await request.post(`${API}/api/scene-creator/projects/${projectId}/parse-shots`, {
      data: { raw_text: text },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    const blob = JSON.stringify(body).toLowerCase();
    expect(blob).toContain("behind");
  });
});
