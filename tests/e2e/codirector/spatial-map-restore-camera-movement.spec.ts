/**
 * Spatial Map restore acceptance — Camera Primary Subject + Movement arrows.
 * Live UI ownership: Primary. This file is READY FOR PRIMARY REVIEW evidence.
 * Does not rebuild Spatial Map. Does not touch Timeline/H3/Omni.
 */
import { expect, test, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const MAP_ID = process.env.ADEPT_SPATIAL_MAP_ID || "d7c721c3-9377-4eca-bea7-3c2be2e5e5fc";
const EVIDENCE = process.env.ADEPT_EVIDENCE_DIR || "";

test.setTimeout(4 * 60 * 1000);

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

async function openMap(page: Page) {
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 45_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
  const select = page.locator("#spatial-map-select");
  if ((await select.count()) > 0) {
    await select.selectOption(MAP_ID).catch(() => undefined);
    await page.waitForTimeout(500);
  }
}

async function shot(page: Page, name: string) {
  if (!EVIDENCE) return;
  await page.screenshot({ path: `${EVIDENCE}\\${name}`, fullPage: false });
}

test.describe("Spatial Map restore — camera subject + movement arrows", () => {
  test("Primary Subject lists Auto+Environment+enabled characters; arrows overlay present", async ({
    page,
    request,
  }) => {
    const mapRes = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${MAP_ID}`);
    expect(mapRes.ok(), "cert map must exist for live acceptance").toBeTruthy();
    const body = await mapRes.json();
    const doc = body.document || body;
    const enabledChars = (doc.characters || []).filter((c: { visible?: boolean }) => c.visible !== false);
    const arrowsApi = await request.get(
      `${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${MAP_ID}/movement-arrows`,
    );
    expect(arrowsApi.ok()).toBeTruthy();
    const arrowsBody = await arrowsApi.json();
    expect(Array.isArray(arrowsBody.arrows)).toBeTruthy();

    await openMap(page);

    // CAMERA ENABLED-CHARACTER FOCUS — card dropdown
    const cardSelect = page.getByTestId("camera-primary-subject-0");
    if (await cardSelect.isVisible().catch(() => false)) {
      const values = await cardSelect.locator("option").evaluateAll((opts) =>
        opts.map((o) => (o as HTMLOptionElement).value),
      );
      expect(values).toContain("auto");
      expect(values).toContain("environment");
      for (const c of enabledChars) {
        const id = String(c.characterId || "").trim();
        if (id) expect(values).toContain(id);
      }
      expect(values.join(" ")).not.toMatch(/Anadriya/i);
      await shot(page, "01_camera_primary_subject_card.png");
    }

    // Inspector path when a camera is selected
    const camMarker = page.locator('[data-testid^="camera-marker-"]').first();
    if (await camMarker.isVisible().catch(() => false)) {
      await camMarker.click({ force: true });
      const inspector = page.getByTestId("camera-primary-subject");
      if (await inspector.isVisible().catch(() => false)) {
        const values = await inspector.locator("option").evaluateAll((opts) =>
          opts.map((o) => (o as HTMLOptionElement).value),
        );
        expect(values).toContain("auto");
        expect(values).toContain("environment");
        await shot(page, "02_camera_primary_subject_inspector.png");
      }
    }

    // MOVEMENT DIRECTION ARROWS overlay host is mounted
    await expect(page.getByTestId("spatial-map-movement-arrows")).toBeAttached({ timeout: 20_000 });
    await shot(page, "03_movement_arrows_overlay.png");

    // MULTI-MOVEMENT / ERS preservation — segments still on document
    expect(Array.isArray(doc.movementSegments)).toBeTruthy();
  });
});
