/**
 * Inspector Location / References / Cast / Voice are advisories.
 * Generate stays available. Gate: Locked only for genuine technical failure.
 */
import { expect, test } from "@playwright/test";
import { TINY_PNG, uploadProjectAsset } from "../codirector/helpers/audit";
import {
  API,
  PROJECT_ID,
  cleanupScenesByPrefix,
  createNamedScene,
  deleteScene,
  ensureBatch,
  getMaster,
  installDirectorWriteGuard,
  openInspector,
  openTimeline,
  patchBatchPrompts,
  waitApiReady,
} from "./masterAuthoring";

const PREFIX = "Inspector Advisory Playwright";
const ADVISORY_PROMPT =
  '@Korri and @Cade sit at #SchnickCoffee. @Korri says, "The coffee is hot."';

async function seedAdvisoryScene(request: Parameters<typeof createNamedScene>[0], name: string) {
  const scene = await createNamedScene(request, name, { durationSec: 15, prompt: ADVISORY_PROMPT });
  const { batchId } = await ensureBatch(request, scene.id);
  await patchBatchPrompts(request, scene.id, batchId, [
    { id: `ps_adv_${Date.now().toString(36)}`, start: 0, length: 10, text: ADVISORY_PROMPT },
  ]);
  return scene;
}

test.describe("Inspector advisory release", () => {
  test.setTimeout(240_000);

  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
    await cleanupScenesByPrefix(request, PREFIX);
  });

  test("B1–B5 B8 — advisories do not lock Generate; reload reconstructs", async ({ page, request }) => {
    const scene = await seedAdvisoryScene(request, `${PREFIX} B15`);
    const guard = installDirectorWriteGuard(page);
    try {
      await openTimeline(page, scene.id);
      await openInspector(page);
      await expect(page.getByTestId("scene-readiness-panel")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("scene-readiness-status")).toContainText(/Ready with \d+ advisories/i);
      await expect(page.getByTestId("scene-readiness-gate")).not.toHaveText(/Locked/i);
      await expect(page.getByTestId("scene-readiness-location-status")).toHaveText(/ADVISORY/i);
      await expect(page.getByTestId("scene-readiness-references-status")).toHaveText(/ADVISORY/i);
      await expect(page.getByTestId("scene-readiness-cast-status")).toHaveText(/ADVISORY/i);
      await expect(page.getByTestId("scene-readiness-voice-status")).toHaveText(/ADVISORY/i);
      await expect(page.getByTestId("timeline-generate-scene")).toBeEnabled();
      await expect(page.getByTestId("timeline-header-generate")).toBeEnabled();

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await openInspector(page);
      await expect(page.getByTestId("scene-readiness-status")).toContainText(/Ready with \d+ advisories/i);
      await expect(page.getByTestId("scene-readiness-gate")).not.toHaveText(/Locked/i);
      await expect(page.getByTestId("timeline-generate-scene")).toBeEnabled();
      guard.assertNone();
    } finally {
      await deleteScene(request, scene.id);
    }
  });

  test("B6 — unavailable generator remains a hard block", async ({ page, request }) => {
    const scene = await seedAdvisoryScene(request, `${PREFIX} B6`);
    try {
      await request.patch(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}`, {
        data: { engine: "generator-not-installed-e2e" },
      });
      await request.post(
        `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${scene.id}/execution-windows/rematerialize`,
        { data: { durationSeconds: 15, generatorId: "generator-not-installed-e2e" } },
      );
      const master = await getMaster(request, scene.id);
      for (const batch of master.batchBlocks || []) {
        if (!batch.id) continue;
        await request.patch(
          `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${scene.id}/batches/${batch.id}`,
          { data: { generatorId: "generator-not-installed-e2e" } },
        );
      }

      await openTimeline(page, scene.id);
      await page.getByTestId("timeline-header-generate").click();
      await expect(page.getByTestId("timeline-action-notice")).toContainText(/not ready/i, { timeout: 15_000 });
    } finally {
      await deleteScene(request, scene.id);
    }
  });

  test("B7 — binding missing names clears those advisories from live state", async ({ page, request }) => {
    const scene = await seedAdvisoryScene(request, `${PREFIX} B7`);
    try {
      await openTimeline(page, scene.id);
      await openInspector(page);
      await expect(page.getByTestId("scene-readiness-location-status")).toHaveText(/ADVISORY/i);

      const env = await uploadProjectAsset(request, PROJECT_ID, {
        name: "schnick.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "SchnickCoffee",
      });
      const korri = await uploadProjectAsset(request, PROJECT_ID, {
        name: "korri.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "Korri",
      });
      const cade = await uploadProjectAsset(request, PROJECT_ID, {
        name: "cade.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "Cade",
      });
      for (const row of [
        { asset_id: env.id, reference_type: "environment", alias: "SchnickCoffee" },
        { asset_id: korri.id, reference_type: "character", alias: "Korri" },
        { asset_id: cade.id, reference_type: "character", alias: "Cade" },
      ]) {
        const bind = await request.post(`${API}/api/projects/${PROJECT_ID}/references`, {
          data: { ...row, scope_type: "scene", scope_id: scene.id, enabled: true },
        });
        expect(bind.ok(), await bind.text()).toBeTruthy();
      }

      await page.getByTestId("timeline-inspector-preflight").click();
      await expect(page.getByTestId("scene-readiness-location-status")).toHaveText(/READY/i, { timeout: 20_000 });
      await expect(page.getByTestId("scene-readiness-cast-status")).toHaveText(/READY/i);
      await expect(page.getByTestId("timeline-generate-scene")).toBeEnabled();
    } finally {
      await deleteScene(request, scene.id);
    }
  });
});
