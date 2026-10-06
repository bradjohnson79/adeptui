/**
 * Express opt-in “Use this image as the Spatial Map”.
 * Named cert project only. Never writes the production Atlas map.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const PRODUCTION_MAP = "e6f64c3b-2533-4549-a476-bf0dcb90d298";
const PRODUCTION_ATLAS = "9f7d4571-9444-41fa-b4c2-29c27919736a";
const MAP_TITLE = "Direct Use Playwright Cert";
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);

test.setTimeout(6 * 60 * 1000);

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

async function listMaps(request: APIRequestContext) {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return (body.documents || body.maps || []) as Array<{ id: string; title?: string; backgroundAssetId?: string | null }>;
}

async function ensureEmptyMap(request: APIRequestContext): Promise<string> {
  const maps = await listMaps(request);
  const existing = maps.find((row) => row.title === MAP_TITLE);
  if (existing) {
    if (existing.backgroundAssetId) {
      await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${existing.id}`, {
        data: { backgroundAssetId: null, notes: `direct-use-empty ${Date.now()}` },
      });
    }
    return existing.id;
  }
  const created = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`, {
    data: { title: MAP_TITLE, notes: "direct-use playwright", sceneDescription: "Playwright direct-use workspace" },
  });
  expect(created.ok()).toBeTruthy();
  const body = await created.json();
  return String(body.document?.id || body.id);
}

async function restoreProduction(request: APIRequestContext) {
  await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${PRODUCTION_MAP}`, {
    data: { notes: `restore-production ${Date.now()}` },
  });
}

async function selectMap(page: Page, mapId: string) {
  const selector = page.getByTestId("spatial-map-selector");
  if (await selector.isVisible().catch(() => false)) {
    await page.locator("#spatial-map-select").selectOption(mapId);
  }
}

test.describe("Spatial Map Express direct-use checkbox", () => {
  test.afterEach(async ({ request }) => {
    try {
      await restoreProduction(request);
    } catch {
      /* API may be mid-recycle; do not fail the suite on cleanup */
    }
  });

  test("checkbox, Use Spatial Map fail/pass, and uncheck restore Generate", async ({ page, request }) => {
    await expect.poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 }).toBeTruthy();
    const mapId = await ensureEmptyMap(request);
    await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`, {
      data: { notes: `direct-use-open ${Date.now()}` },
    });

    await openSpatialMap(page);
    await selectMap(page, mapId);
    const form = page.getByTestId("spatial-map-express-form");
    await expect(form).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("spatial-map-use-as-atlas")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-generate")).toHaveAttribute("aria-label", "Generate Spatial Map");

    const executions: Array<Record<string, unknown>> = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && /\/executions\/?$/.test(req.url())) {
        try {
          executions.push(req.postDataJSON() as Record<string, unknown>);
        } catch {
          /* ignore */
        }
      }
    });

    await page.getByTestId("spatial-map-reference-file").setInputFiles({
      name: "eye-level.png",
      mimeType: "image/png",
      buffer: TINY_PNG,
    });
    await expect(page.getByTestId("spatial-map-selected-reference")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("spatial-map-use-as-atlas")).toBeVisible();
    await page.getByTestId("spatial-map-use-as-atlas").check();
    await expect(page.getByTestId("spatial-map-generate")).toHaveAttribute("aria-label", "Use Spatial Map");
    const before = executions.length;
    await page.getByTestId("spatial-map-generate").click();
    await expect(page.getByTestId("spatial-map-generate-error")).toContainText("finished top-down Spatial Map", {
      timeout: 20_000,
    });
    expect(executions.length).toBe(before);
    await expect(form).toBeVisible();

    await page.getByTestId("spatial-map-use-as-atlas").uncheck();
    await expect(page.getByTestId("spatial-map-generate")).toHaveAttribute("aria-label", "Generate Spatial Map");

    await page.getByTestId("spatial-map-remove-reference").click();
    await expect(page.getByTestId("spatial-map-use-as-atlas")).toHaveCount(0);

    const classify = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/atlas-source/classify`, {
      data: { assetId: PRODUCTION_ATLAS, intendedRoute: "assign" },
    });
    if (classify.ok()) {
      const verdict = await classify.json();
      if (verdict.action === "assign") {
        await page.getByTestId("spatial-map-select-library").click();
        const picker = page.getByRole("dialog").or(page.locator("[data-testid='entity-picker']")).first();
        if (await picker.isVisible({ timeout: 8_000 }).catch(() => false)) {
          await page.keyboard.press("Escape");
        }
        await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${mapId}`, {
          data: {
            backgroundAssetId: PRODUCTION_ATLAS,
            geometrySource: "supplied",
            notes: `direct-use-assigned ${Date.now()}`,
          },
        });
        await page.reload();
        await dismissOnboarding(page);
        await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
        await selectMap(page, mapId);
        await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });
        const save = page.getByTestId("spatial-map-save");
        if (await save.isEnabled().catch(() => false)) {
          await save.click();
          await expect(page.getByTestId("spatial-map-save-state")).toContainText(/saved|up to date|saved/i, {
            timeout: 20_000,
          });
        }
        await page.reload();
        await dismissOnboarding(page);
        await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
        await selectMap(page, mapId);
        await expect(page.getByTestId("active-atlas-panel")).toBeVisible({ timeout: 30_000 });
      }
    }
  });
});
