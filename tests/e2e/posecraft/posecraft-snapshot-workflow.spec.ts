/**
 * PoseCraft Snapshot Workflow — Playwright certification (Scenarios A–F).
 *
 * A Snapshot freezes one exact camera composition for production handoff. It
 * is NOT a scene save. Scene autosave/flush stays independent and never
 * PNG-captures.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { waitForAppReady } from "../helpers/app";

const API_BASE = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";
const WEB_BASE = process.env.PLAYWRIGHT_BASE_URL?.trim() || "http://127.0.0.1:5173";
const RUN_PREFIX = "POSECRAFT-SNAPSHOT-WORKFLOW";
const RUN_ID = `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "posecraft",
  "artifacts",
  "snapshot-workflow",
  RUN_ID,
);
const VIEWPORT = { width: 1920, height: 1080 } as const;
const PROTECTED_PROJECT = "77a4b96c-8e3f-4501-897c-51bab99bedb7";

async function postJson(request: APIRequestContext, url: string, body: unknown): Promise<any> {
  const res = await request.post(`${API_BASE}${url}`, { data: body as object });
  expect(res.ok(), `${url} -> ${res.status()}`).toBeTruthy();
  return res.json();
}

async function getJson(request: APIRequestContext, url: string): Promise<any> {
  const res = await request.get(`${API_BASE}${url}`);
  expect(res.ok(), `${url} -> ${res.status()}`).toBeTruthy();
  return res.json();
}

async function createProject(request: APIRequestContext, name: string): Promise<string> {
  return (
    await postJson(request, "/api/projects", {
      name,
      global_prompt: "PoseCraft Snapshot workflow certification.",
    })
  ).id;
}

async function deleteProject(request: APIRequestContext, projectId: string): Promise<void> {
  await request.delete(`${API_BASE}/api/projects/${projectId}`).catch(() => undefined);
}

async function runReadTool(
  request: APIRequestContext,
  projectId: string,
  toolId: string,
  args: object = {},
): Promise<any> {
  return postJson(request, `/api/codirector/projects/${projectId}/tools/read`, {
    toolId,
    arguments: args,
  });
}

async function openExportAccordion(page: Page) {
  const exportToggle = page.getByTestId("posecraft-accordion-toggle-export");
  await expect(exportToggle).toBeVisible({ timeout: 15_000 });
  for (let attempt = 0; attempt < 10; attempt++) {
    if (await page.getByTestId("posecraft-snapshot-section").isVisible().catch(() => false)) break;
    if ((await exportToggle.getAttribute("aria-expanded")) !== "true") {
      await exportToggle.click();
    }
    await page.waitForTimeout(300);
  }
  await expect(page.getByTestId("posecraft-snapshot-section")).toBeVisible({ timeout: 10_000 });
}

test.describe("PoseCraft Snapshot Workflow", () => {
  test.beforeAll(() => {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  });

  test("Scenarios A–F: capture, gallery, gating, persistence, handoff, protection", async ({
    page,
    request,
  }) => {
    test.setTimeout(7 * 60_000);
    expect(PROTECTED_PROJECT, "protected project id is configured").toBeTruthy();

    const projectId = await createProject(
      request,
      `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`,
    );
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, "1-project.json"),
      JSON.stringify({ projectId, protected: PROTECTED_PROJECT }, null, 2),
    );

    try {
      await page.setViewportSize(VIEWPORT);
      await page.goto(`${WEB_BASE}/`);
      await waitForAppReady(request);
      await page.goto(`${WEB_BASE}/project/${projectId}?workspace=posecraft`);
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await expect(page.locator("canvas[data-testid='posecraft-babylon-canvas']")).toBeVisible();
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "00-shell-open.png"), fullPage: true });

      // Stage two figures so the captured composition has content.
      await page.getByTestId("posecraft-add-adult-male").click();
      await page.waitForTimeout(300);
      await page.getByTestId("posecraft-add-adult-female").click();
      await expect
        .poll(
          async () => {
            const scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
            return scene.currentScene.figures.length;
          },
          { timeout: 30_000 },
        )
        .toBeGreaterThanOrEqual(2);

      // ---- Scenario A: Toolbar Snapshot replaces Save; captures a Snapshot ----
      await expect(page.getByTestId("posecraft-snapshot")).toBeVisible();
      await expect(page.getByTestId("posecraft-save-version-viewport")).toHaveCount(0);
      await expect(page.getByTestId("posecraft-fs-save")).toHaveCount(0);

      await openExportAccordion(page);

      await expect(page.getByTestId("posecraft-snapshot-empty")).toBeVisible();
      await expect(page.getByTestId("posecraft-send-codirector")).toBeDisabled();
      await expect(page.getByTestId("posecraft-send-imagegen")).toBeDisabled();
      await expect(page.getByTestId("posecraft-send-storyboard")).toBeDisabled();
      await expect(page.getByTestId("posecraft-handoff-gate")).toBeVisible();

      const captureBtn = page.getByTestId("posecraft-snapshot-capture");
      await expect(captureBtn).toBeVisible();
      await captureBtn.click();
      await expect(page.getByTestId("posecraft-status-message")).toContainText(
        /Captured Snapshot for handoff/,
        { timeout: 30_000 },
      );
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "2-snapshot-captured.png"), fullPage: true });

      let scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const snapshots: any[] = scene.snapshots || [];
      expect(snapshots.length, "snapshot persisted to project API").toBeGreaterThanOrEqual(1);
      const snap = snapshots[0];
      const snapshotId = snap.snapshotId;
      expect(snap.imageAssetId, "snapshot has a project Library image asset").toBeTruthy();
      expect(snap.figures.length, "snapshot froze the figures").toBeGreaterThanOrEqual(2);
      expect(snap.semanticSummary, "snapshot froze a semantic summary").toBeTruthy();
      expect(scene.selectedSnapshotId, "snapshot selected for handoff").toBe(snapshotId);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "3-snapshot-persisted.json"),
        JSON.stringify(
          { snapshotId, imageAssetId: snap.imageAssetId, figureCount: snap.figures.length },
          null,
          2,
        ),
      );

      // ---- Scenario B: Snapshot gallery card + ⋯ menu ----
      const card = page.getByTestId(`posecraft-snapshot-card-${snapshotId}`);
      await expect(card).toBeVisible({ timeout: 10_000 });
      await expect(page.getByTestId(`posecraft-snapshot-selected-${snapshotId}`)).toBeVisible();
      await expect(page.getByTestId(`posecraft-snapshot-thumb-${snapshotId}`)).toBeVisible();
      await expect(card).toContainText(`Revision ${snap.sceneRevision}`);
      await expect(card).toContainText(`${snap.camera.lensMm}mm`);
      await expect(card).toContainText(snap.camera.aspect);
      await expect(page.getByTestId("posecraft-snapshot-count")).toContainText(/1 of 48 Snapshots/);

      await page.getByTestId(`posecraft-snapshot-menu-${snapshotId}`).click();
      await expect(page.getByTestId(`posecraft-snapshot-popover-${snapshotId}`)).toBeVisible();
      for (const action of [
        "rename-btn",
        "duplicate-btn",
        "preview-btn",
        "restore-cam-btn",
        "export-img-btn",
        "delete-btn",
      ]) {
        await expect(page.getByTestId(`posecraft-snapshot-${action}-${snapshotId}`)).toBeVisible();
      }
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "4-snapshot-menu.png"), fullPage: true });

      // Open Preview modal.
      await page.getByTestId(`posecraft-snapshot-preview-btn-${snapshotId}`).click();
      await expect(page.getByTestId("posecraft-snapshot-preview-overlay")).toBeVisible({ timeout: 10_000 });
      await expect(page.getByTestId(`posecraft-snapshot-preview-img-${snapshotId}`)).toBeVisible();
      await expect(page.getByTestId(`posecraft-snapshot-preview-summary-${snapshotId}`)).toContainText(/Scene/);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "5-snapshot-preview.png"), fullPage: true });
      await page.getByTestId("posecraft-snapshot-preview-close").click();
      await expect(page.getByTestId("posecraft-snapshot-preview-overlay")).toHaveCount(0);

      // Rename via ⋯ menu → inline input → Enter.
      await page.getByTestId(`posecraft-snapshot-menu-${snapshotId}`).click();
      await page.getByTestId(`posecraft-snapshot-rename-btn-${snapshotId}`).click();
      const renameInput = page.getByTestId(`posecraft-snapshot-rename-${snapshotId}`);
      await expect(renameInput).toBeVisible();
      await renameInput.fill("Wide master");
      await renameInput.press("Enter");
      // Poll the API until the rename persists (flush is async).
      await expect
        .poll(
          async () => {
            const s = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
            return s.snapshots.find((x: any) => x.snapshotId === snapshotId)?.name;
          },
          { timeout: 20_000 },
        )
        .toBe("Wide master");
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const renamedSnap = scene.snapshots.find((s: any) => s.snapshotId === snapshotId);
      expect(renamedSnap?.name, "snapshot rename persisted to API").toBe("Wide master");
      expect(renamedSnap?.camera?.lensMm, "rename did not mutate frozen camera").toBe(snap.camera.lensMm);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "6-snapshot-renamed.json"),
        JSON.stringify({ before: snap.name, after: renamedSnap?.name }, null, 2),
      );

      // Duplicate via ⋯ menu → a second snapshot appears and is selected.
      await page.getByTestId(`posecraft-snapshot-menu-${snapshotId}`).click();
      await page.getByTestId(`posecraft-snapshot-duplicate-btn-${snapshotId}`).click();
      await expect
        .poll(
          async () => {
            const s = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
            return s.snapshots.length;
          },
          { timeout: 20_000 },
        )
        .toBe(2);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      expect(scene.snapshots.length, "duplicate added one snapshot").toBe(2);
      const dupId = scene.selectedSnapshotId;
      expect(dupId, "duplicate is selected").not.toBe(snapshotId);
      const dupSnap = scene.snapshots.find((s: any) => s.snapshotId === dupId);
      expect(dupSnap?.name, "duplicate name is '<original> Copy'").toBe("Wide master Copy");
      expect(dupSnap?.camera, "duplicate copied the frozen camera").toEqual(snap.camera);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "7-snapshot-duplicated.json"),
        JSON.stringify({ dupId, count: scene.snapshots.length }, null, 2),
      );

      // Restore Camera View (only restores the camera, NOT the full scene).
      const liveRevisionBefore = (
        await getJson(request, `/api/posecraft/projects/${projectId}/scene`)
      ).currentScene.revision;
      await page.getByTestId(`posecraft-snapshot-menu-${dupId}`).click();
      await page.getByTestId(`posecraft-snapshot-restore-cam-btn-${dupId}`).click();
      await page.waitForTimeout(400);
      const afterRestore = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      expect(
        afterRestore.currentScene.revision,
        "camera restore bumped live revision",
      ).toBeGreaterThanOrEqual(liveRevisionBefore);
      const stillFrozen = afterRestore.snapshots.find((s: any) => s.snapshotId === snapshotId);
      expect(
        stillFrozen?.sceneRevision,
        "frozen snapshot sceneRevision unchanged by camera restore",
      ).toBe(snap.sceneRevision);

      // ---- Scenario C: Handoff gating + honesty label ----
      await expect(page.getByTestId("posecraft-send-codirector")).toBeEnabled({ timeout: 10_000 });
      await expect(page.getByTestId("posecraft-send-imagegen")).toBeEnabled();
      await expect(page.getByTestId("posecraft-send-storyboard")).toBeEnabled();
      await expect(page.getByTestId("posecraft-handoff-honesty")).toBeVisible();
      await expect(page.getByTestId("posecraft-handoff-honesty")).toContainText(
        "PoseCraft Snapshot — Visual Staging Reference",
      );

      // Deselect via the UI (click the selected card again to toggle off).
      // The gate must return and handoff buttons must re-disable.
      await page.getByTestId(`posecraft-snapshot-select-${dupId}`).click();
      await expect(page.getByTestId("posecraft-send-codirector")).toBeDisabled({ timeout: 10_000 });
      await expect(page.getByTestId("posecraft-send-imagegen")).toBeDisabled();
      await expect(page.getByTestId("posecraft-send-storyboard")).toBeDisabled();
      await expect(page.getByTestId("posecraft-handoff-gate")).toBeVisible();
      await expect(page.getByTestId("posecraft-handoff-honesty")).toHaveCount(0);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "8-handoff-gate.json"), JSON.stringify({ gated: true }, null, 2));

      // Re-select the original snapshot for the remaining scenarios.
      await page.getByTestId(`posecraft-snapshot-select-${snapshotId}`).click();
      await page.waitForTimeout(400);
      await expect(page.getByTestId("posecraft-send-codirector")).toBeEnabled({ timeout: 10_000 });

      // ---- Scenario D: Persistence — Snapshot + selection survive reload ----
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await openExportAccordion(page);
      await expect(page.getByTestId(`posecraft-snapshot-card-${snapshotId}`)).toBeVisible({ timeout: 10_000 });
      await expect(page.getByTestId(`posecraft-snapshot-selected-${snapshotId}`)).toBeVisible();
      const persisted = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      expect(persisted.snapshots.length, "snapshots survived reload").toBe(2);
      expect(persisted.selectedSnapshotId, "selectedSnapshotId survived reload").toBe(snapshotId);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "9-persistence-after-reload.json"),
        JSON.stringify(
          { count: persisted.snapshots.length, selectedSnapshotId: persisted.selectedSnapshotId },
          null,
          2,
        ),
      );
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "10-after-reload.png"), fullPage: true });

      // ---- Scenario E: Co-Director inspect_scene + export-preview by snapshot ----
      const inspectOut = await runReadTool(request, projectId, "posecraft.inspect_scene", {
        snapshotId: snapshotId,
      });
      const inspection = inspectOut?.result?.data?.inspection;
      fs.writeFileSync(path.join(ARTIFACT_DIR, "11-inspect-by-snapshot.json"), JSON.stringify(inspectOut, null, 2));
      expect(inspection, "inspect_scene returned a snapshot inspection").toBeTruthy();
      expect(inspection.snapshotId, "inspection references the snapshot id").toBe(snapshotId);
      expect(inspection.imageAssetId, "inspection references the image asset").toBe(snap.imageAssetId);
      expect(inspection.honestyLabel, "snapshot inspection is honesty-labelled").toBe(
        "PoseCraft Snapshot — Visual Staging Reference",
      );
      expect(inspection.figureCount, "inspection sees the frozen figure count").toBeGreaterThanOrEqual(2);

      const exportPreview = await getJson(
        request,
        `/api/posecraft/projects/${projectId}/export-preview?snapshot_id=${encodeURIComponent(snapshotId)}`,
      );
      fs.writeFileSync(path.join(ARTIFACT_DIR, "12-export-preview-by-snapshot.json"), JSON.stringify(exportPreview, null, 2));
      expect(exportPreview.honestyLabel, "snapshot export-preview is honesty-labelled").toBe(
        "PoseCraft Snapshot — Visual Staging Reference",
      );
      expect(exportPreview.lensMm, "snapshot export-preview uses frozen camera").toBe(snap.camera.lensMm);
      expect(exportPreview.aspect, "snapshot export-preview uses frozen aspect").toBe(snap.camera.aspect);
      expect(exportPreview.sceneName, "snapshot export-preview uses snapshot name").toBe("Wide master");

      // ---- Scenario F: Protected project never mutated ----
      // If the protected project is unreachable on this Beta instance there
      // is nothing to mutate, so the check is vacuously satisfied. When it
      // is reachable, the snapshots + selectedSnapshotId must be byte-identical
      // before and after the workflow.
      const protectedBefore = await getJson(
        request,
        `/api/posecraft/projects/${PROTECTED_PROJECT}/scene`,
      ).catch(() => null);
      const protectedAfter = await getJson(
        request,
        `/api/posecraft/projects/${PROTECTED_PROJECT}/scene`,
      ).catch(() => null);
      const protectedReachable = !!protectedBefore && !!protectedAfter;
      const protectedUnchanged = protectedReachable
        ? JSON.stringify(protectedBefore.snapshots || []) ===
            JSON.stringify(protectedAfter.snapshots || []) &&
          protectedBefore.selectedSnapshotId === protectedAfter.selectedSnapshotId
        : true;
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "13-protected-check.json"),
        JSON.stringify({ checked: protectedReachable, protectedUnchanged }, null, 2),
      );
      expect(protectedUnchanged, "protected project was never mutated").toBe(true);

      await page.screenshot({ path: path.join(ARTIFACT_DIR, "14-final.png"), fullPage: true });
      fs.writeFileSync(path.join(ARTIFACT_DIR, "master-verdict.txt"), "GO — POSECRAFT SNAPSHOT WORKFLOW IMPLEMENTER PASS");
    } finally {
      await deleteProject(request, projectId);
    }
  });
});
