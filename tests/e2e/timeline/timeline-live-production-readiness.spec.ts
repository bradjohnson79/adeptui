/**
 * Production Readiness is computed from the Cade establishing scene bindings.
 * No Preflight seed. Remove/restore Venture must flip References BLOCKED ↔ READY.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_CADE_PROJECT_ID || "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";
const SCENE_ID = process.env.ADEPT_CADE_SCENE_ID || "8a385844-3e0d-48e3-a759-d3fb242cd392";
const UI = process.env.ADEPT_UI_ORIGIN || "http://127.0.0.1:5173";

async function getJson(request: APIRequestContext, path: string) {
  const res = await request.get(`${API}${path}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function openRightInspector(page: Page) {
  const rightToggle = page.getByTestId("timeline-drawer-right-toggle");
  await expect(rightToggle).toBeVisible();
  if ((await rightToggle.getAttribute("aria-expanded")) !== "true") {
    await rightToggle.click();
  }
  await expect(rightToggle).toHaveAttribute("aria-expanded", "true");
  const tab = page.getByTestId("timeline-tab-inspector");
  if (await tab.isVisible().catch(() => false)) {
    if ((await tab.getAttribute("aria-selected")) !== "true") {
      await tab.click();
    }
  }
  await expect(page.getByTestId("timeline-inspector")).toBeVisible({ timeout: 20_000 });
}

async function expectLiveReady(page: Page) {
  await expect(page.getByTestId("scene-readiness-location-status")).toHaveText("READY");
  await expect(page.getByTestId("scene-readiness-location-items")).toContainText(/Earth Horizon/i);
  await expect(page.getByTestId("scene-readiness-references-status")).toHaveText("READY");
  const refs = page.getByTestId("scene-readiness-references-items");
  await expect(refs).toContainText(/Earth Horizon/i);
  await expect(refs).toContainText(/Venture Spaceship/i);
  await expect(refs).toContainText(/Cade'?s Starfighter/i);
  await expect(page.getByTestId("scene-readiness-cast-status")).toHaveText("NOT REQUIRED");
  await expect(page.getByTestId("scene-readiness-voice-status")).toHaveText("NOT REQUIRED");
}

test.describe("Live Production Readiness — Cade establishing scene", () => {
  test.setTimeout(180_000);
  test.skip(
    process.env.ADEPT_ALLOW_CADE_MUTATION !== "1" && process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1",
    "Requires ADEPT_ALLOW_CADE_MUTATION=1",
  );

  test("computes from scene bindings, survives reload, blocks when Venture is removed", async ({
    page,
    request,
  }) => {
    await expect
      .poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 })
      .toBeTruthy();

    const listed = await getJson(
      request,
      `/api/projects/${PROJECT_ID}/references?scope_type=scene&scope_id=${SCENE_ID}`,
    );
    const items = listed.items || [];
    const venture = items.find((row: { alias?: string; display_token?: string }) =>
      /venture/i.test(`${row.alias || ""} ${row.display_token || ""}`),
    );
    expect(venture?.id, "Venture binding must exist on Cade Scene 1").toBeTruthy();
    const snapshot = {
      asset_id: venture.asset_id,
      scope_type: venture.scope_type || "scene",
      scope_id: venture.scope_id || SCENE_ID,
      reference_type: venture.reference_type || "prop",
      alias: venture.alias,
      usage_modes: venture.usage_modes || ["appearance"],
      reference_roles: venture.reference_roles || ["prop"],
    };

    try {
      await page.goto(`${UI}/project/${PROJECT_ID}?workspace=timeline&sceneId=${SCENE_ID}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await openRightInspector(page);
      await expect(page.getByTestId("scene-readiness-panel")).toBeVisible();
      await expectLiveReady(page);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await openRightInspector(page);
      await expectLiveReady(page);

      const removed = await request.delete(`${API}/api/projects/${PROJECT_ID}/references/${venture.id}`);
      expect(removed.ok(), await removed.text()).toBeTruthy();

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await openRightInspector(page);
      await expect(page.getByTestId("scene-readiness-references-status")).toHaveText("BLOCKED");
      await expect(page.getByTestId("scene-readiness-references-missing")).toContainText(/Venture/i);

      const restored = await request.post(`${API}/api/projects/${PROJECT_ID}/references`, {
        data: snapshot,
      });
      expect(restored.ok(), await restored.text()).toBeTruthy();

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await openRightInspector(page);
      await expectLiveReady(page);
    } finally {
      const after = await getJson(
        request,
        `/api/projects/${PROJECT_ID}/references?scope_type=scene&scope_id=${SCENE_ID}`,
      );
      const hasVenture = (after.items || []).some((row: { alias?: string; display_token?: string }) =>
        /venture/i.test(`${row.alias || ""} ${row.display_token || ""}`),
      );
      if (!hasVenture) {
        await request.post(`${API}/api/projects/${PROJECT_ID}/references`, { data: snapshot });
      }
    }
  });
});
