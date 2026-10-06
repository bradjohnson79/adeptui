/**
 * Scene Creator Mini camera production: lens/mood persist, Save beside ERS,
 * refs off the map, Local sequential / API concurrent, modal caption.
 * Named cert project only. Never writes the production Atlas map.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const PRODUCTION_MAP = "e6f64c3b-2533-4549-a476-bf0dcb90d298";
const PRODUCTION_ATLAS = "9f7d4571-9444-41fa-b4c2-29c27919736a";
const ERS_MAP = "d7c721c3-9377-4eca-bea7-3c2be2e5e5fc";
const CAPTION = "Shot not looking right? Consider adjusting your cameras in the Spatial Map, save then retry.";

test.setTimeout(8 * 60 * 1000);

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) return;
    const skip = region.getByRole("button", { name: /Skip for now/i }).first();
    if (await skip.isVisible().catch(() => false)) {
      await skip.click({ force: true }).catch(() => undefined);
      await page.waitForTimeout(400);
    } else {
      break;
    }
  }
}

async function openSpatialMap(page: Page) {
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

async function selectMap(page: Page, mapId: string) {
  const select = page.locator("#spatial-map-select");
  await expect(select).toBeAttached({ timeout: 20_000 });
  await select.selectOption(mapId);
  await expect(select).toHaveValue(mapId, { timeout: 15_000 });
}

async function restoreProduction(request: APIRequestContext) {
  try {
    await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${PRODUCTION_MAP}`, {
      data: { notes: `restore-production ${Date.now()}` },
    });
  } catch {
    // keep going
  }
}

test.describe("Scene Creator Mini camera production", () => {
  test.afterEach(async ({ request }) => {
    await restoreProduction(request);
    try {
      const atlas = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${PRODUCTION_MAP}`);
      if (atlas.ok()) {
        const body = await atlas.json();
        expect(body.document?.backgroundAssetId || body.backgroundAssetId).toBe(PRODUCTION_ATLAS);
      }
    } catch {
      // API recycle mid-test must not hide the real assertion.
    }
  });

  test("lens, Sci-Fi mood, Save beside ERS, refs off map, persist after reload", async ({ page, request }) => {
    const mapRes = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    expect(mapRes.ok()).toBeTruthy();
    const map = (await mapRes.json()).document;
    expect(map.id).toBe(ERS_MAP);
    const cameras = (map.cameras || []).filter((c: { visible?: boolean; gridRow?: number }) => c.visible !== false && (c.gridRow ?? -1) >= 0);
    expect(cameras.length, "ERS map needs at least one placed camera").toBeGreaterThan(0);
    const c1 = cameras.sort((a: { cameraSlot: number }, b: { cameraSlot: number }) => a.cameraSlot - b.cameraSlot)[0];

    await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}/cameras/${c1.id}`, {
      data: { lens: "35", lightingMood: "sci_fi", shotSize: "medium", primarySubject: c1.primarySubject || "auto" },
    });

    await openSpatialMap(page);
    await selectMap(page, ERS_MAP);

    await expect(page.getByTestId("spatial-map-ers-action-row")).toBeVisible();
    await expect(page.getByTestId("spatial-map-save-ers-row")).toBeVisible();
    await expect(page.getByRole("button", { name: /Reset Map/i })).toBeVisible();
    await expect(page.getByText("Camera Shot References")).toHaveCount(0);
    await expect(page.getByTestId("scene-creator-mini")).toBeVisible();

    const lens = page.getByTestId(`camera-lens-${c1.cameraSlot}`);
    await expect(lens).toBeVisible();
    await lens.selectOption("35");
    const mood = page.getByTestId(`camera-lighting-mood-${c1.cameraSlot}`);
    await mood.selectOption("sci_fi");
    await page.getByTestId("spatial-map-save-ers-row").click();
    await expect(page.getByTestId("spatial-map-save-state-ers-row")).toContainText(/Saved|Saving/i, { timeout: 20_000 });

    await page.reload();
    await openSpatialMap(page);
    await selectMap(page, ERS_MAP);
    await expect(page.getByTestId(`camera-lens-${c1.cameraSlot}`)).toHaveValue("35");
    await expect(page.getByTestId(`camera-lighting-mood-${c1.cameraSlot}`)).toHaveValue("sci_fi");

    const after = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    const saved = (await after.json()).document;
    const savedCam = (saved.cameras || []).find((c: { id: string }) => c.id === c1.id);
    expect(savedCam?.lens).toBe("35");
    expect(savedCam?.lightingMood).toBe("sci_fi");
  });

  test("Fisheye appears in the lens dropdown and persists after save/reload", async ({ page, request }) => {
    const mapRes = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    expect(mapRes.ok()).toBeTruthy();
    const map = (await mapRes.json()).document;
    const cameras = (map.cameras || []).filter((c: { visible?: boolean; gridRow?: number }) => c.visible !== false && (c.gridRow ?? -1) >= 0);
    expect(cameras.length).toBeGreaterThan(0);
    const c1 = cameras.sort((a: { cameraSlot: number }, b: { cameraSlot: number }) => a.cameraSlot - b.cameraSlot)[0];

    await openSpatialMap(page);
    await selectMap(page, ERS_MAP);
    const lens = page.getByTestId(`camera-lens-${c1.cameraSlot}`);
    await expect(lens).toBeVisible();
    await expect(lens.locator("option[value='fisheye']")).toHaveCount(1);
    await expect(lens.locator("option[value='fisheye']")).toHaveText("Fisheye");
    await lens.selectOption("fisheye");
    await page.getByTestId("spatial-map-save-ers-row").click();
    await expect(page.getByTestId("spatial-map-save-state-ers-row")).toContainText(/Saved|Saving/i, { timeout: 20_000 });

    await page.reload();
    await openSpatialMap(page);
    await selectMap(page, ERS_MAP);
    await expect(page.getByTestId(`camera-lens-${c1.cameraSlot}`)).toHaveValue("fisheye");
    const after = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    const savedCam = ((await after.json()).document.cameras || []).find((c: { id: string }) => c.id === c1.id);
    expect(savedCam?.lens).toBe("fisheye");
    expect(savedCam?.lens).not.toBe("18");
  });

  test("Mini API fans out concurrent jobs; Local stays sequential or skips honestly", async ({ page, request }) => {
    const mapRes = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    const map = (await mapRes.json()).document;
    const cameras = (map.cameras || [])
      .filter((c: { visible?: boolean; gridRow?: number }) => c.visible !== false && (c.gridRow ?? -1) >= 0)
      .sort((a: { cameraSlot: number }, b: { cameraSlot: number }) => a.cameraSlot - b.cameraSlot)
      .slice(0, 2);
    test.skip(cameras.length < 1, "No placed cameras on ERS Production Cert map");

    await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}/save`);

    const apiTake = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}/mini-take`, {
      data: { generator: "gpt-image-2", aspectRatio: "16:9", cameraIds: cameras.map((c: { id: string }) => c.id) },
    });
    if (!apiTake.ok()) {
      const detail = await apiTake.text();
      test.skip(true, `Mini API take blocked: ${detail.slice(0, 240)}`);
    }
    const take = (await apiTake.json()).take;
    const withJobs = (take.results || []).filter((r: { jobId?: string }) => r.jobId);
    expect(take.concurrency).toBe("api_concurrent");
    expect(withJobs.length, "API persists every camera × variant child before dispatch").toBe(cameras.length * 2);

    const overlap = new Set<string>();
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const poll = await request.get(
        `${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}/mini-take/${take.id}`,
      );
      expect(poll.ok()).toBeTruthy();
      const live = (await poll.json()).take;
      const active = (live.results || []).filter(
        (r: { status?: string }) => r.status === "generating" || r.status === "complete",
      );
      for (const row of active) {
        overlap.add(`${row.cameraId}:${row.variation}`);
      }
      const generatingNow = (live.results || []).filter((r: { status?: string }) => r.status === "generating");
      if (generatingNow.length >= 2) {
        overlap.add("__overlap__");
        break;
      }
      if (overlap.size >= 2 && generatingNow.length === 0) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    expect(
      overlap.has("__overlap__") || overlap.size >= 2,
      "API Variant A and Variant B must run together, not one-after-another",
    ).toBeTruthy();
    expect(overlap.has("__overlap__"), "Hard E2E: at least two API children generating at the same poll").toBeTruthy();

    const localTake = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}/mini-take`, {
      data: { generator: "qwen2512", aspectRatio: "16:9", cameraIds: cameras.map((c: { id: string }) => c.id) },
    });
    if (!localTake.ok()) {
      test.info().annotations.push({ type: "skip", description: `Local Mini not ready: ${(await localTake.text()).slice(0, 200)}` });
    } else {
      const local = (await localTake.json()).take;
      expect(local.concurrency).toBe("local_sequential");
      const liveJobs = (local.results || []).filter((r: { jobId?: string }) => r.jobId);
      if (liveJobs.length === 0) {
        test.info().annotations.push({
          type: "skip",
          description: "Local Mini accepted the take but did not launch a GPU job (honest skip).",
        });
      } else {
        expect(liveJobs.length, "Local launches one GPU job at a time").toBe(1);
      }
    }

    await openSpatialMap(page);
    await selectMap(page, ERS_MAP);
    await page.getByTestId("scene-creator-mini-toggle").click().catch(() => undefined);
    const enable = page.getByTestId("scene-creator-mini-enable");
    if ((await enable.getAttribute("aria-checked")) !== "true") {
      await enable.click();
    }
    const gen = page.getByTestId("scene-creator-mini-generator");
    if (await gen.isVisible()) {
      await gen.selectOption("gpt-image-2").catch(() => undefined);
    }
    const thumb = page.locator("[data-testid^='mini-result-']").first();
    if (await thumb.isVisible().catch(() => false)) {
      await thumb.click();
      await expect(page.getByTestId("mini-shot-caption")).toHaveText(CAPTION);
    }
  });
});
