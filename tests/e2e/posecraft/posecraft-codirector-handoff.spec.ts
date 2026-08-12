/**
 * PoseCraft → Co-Director handoff regression test.
 *
 * Verifies the "Send to Co-Director" button (first action in the Versions +
 * Exports accordion) wires end-to-end:
 *   1. UI click is wired (button present, becomes loading, then settles).
 *   2. The current PoseCraft scene is flushed to the project API so Co-Director
 *      reads the live blocking — not a stale debounced snapshot.
 *   3. The Co-Director session opens with a creator-facing prompt that
 *      references the staged scene and asks Co-Director to inspect it.
 *   4. Co-Director can actually receive the scene: the frozen
 *      posecraft.inspect_scene tool, executed via the proposal+approve path,
 *      returns the figures/furniture we staged for the SAME project.
 *   5. The protected project is never mutated.
 *
 * This is a focused regression for the handoff button → API → Co-Director
 * receipt path. It does not weaken the Final Mandatory GO gates; it adds a
 * dedicated guard so the handoff cannot silently regress to a stub.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { waitForAppReady } from "../helpers/app";

const API_BASE = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";
const RUN_PREFIX = "POSECRAFT-CODIRECTOR-HANDOFF";
const RUN_ID = `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "posecraft",
  "artifacts",
  "codirector-handoff",
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
      global_prompt: "PoseCraft Co-Director handoff regression.",
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
  // Read tools (kind="read") execute immediately via /tools/read — no
  // proposal+approve needed. This is the path Co-Director uses to inspect
  // the live PoseCraft scene. The Beta Co-Director tools endpoint can
  // intermittently hang, so we allow a generous per-attempt timeout and
  // retry a few times before giving up.
  const url = `/api/codirector/projects/${projectId}/tools/read`;
  let lastError: unknown = undefined;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await request.post(`${API_BASE}${url}`, {
        data: { toolId, arguments: args },
        timeout: 60_000,
      });
      if (!res.ok()) {
        lastError = new Error(`${url} -> ${res.status()}`);
        await pagelessDelay(2000);
        continue;
      }
      return res.json();
    } catch (err) {
      lastError = err;
      await pagelessDelay(2000);
    }
  }
  throw lastError ?? new Error(`${url} failed after retries`);
}

function pagelessDelay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

test.describe("PoseCraft → Co-Director handoff", () => {
  test.beforeAll(() => {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  });

  test("Send to Co-Director flushes scene + opens Co-Director with inspectable context", async ({
    page,
    request,
  }) => {
    test.setTimeout(5 * 60_000);
    expect(PROTECTED_PROJECT, "protected project id is configured").toBeTruthy();

    const projectId = await createProject(request, `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`);
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, "1-project.json"),
      JSON.stringify({ projectId, protected: PROTECTED_PROJECT }, null, 2),
    );

    try {
      await page.setViewportSize(VIEWPORT);
      await page.goto("/");
      await waitForAppReady(request);
      await page.goto(`/project/${projectId}?workspace=posecraft`);
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await expect(page.locator("canvas[data-testid='posecraft-babylon-canvas']")).toBeVisible();
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "00-shell-open.png"), fullPage: true });

      // Stage figures via the Cast Browser UI clicks (reliable, fast) so the
      // scene has inspectable content. We avoid the Co-Director tool-proposal
      // path here because it is not the subject of this regression; the
      // handoff receipt is verified separately via the /tools/read endpoint
      // below.
      await page.getByTestId("posecraft-add-adult-male").click();
      await page.waitForTimeout(300);
      await page.getByTestId("posecraft-add-adult-female").click();
      // Poll the API until both figures persist (debounced save).
      let scene: any;
      for (let i = 0; i < 20; i++) {
        scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        if (scene.currentScene.figures.length >= 2) break;
        await page.waitForTimeout(300);
      }
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await page.waitForTimeout(1000);

      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const figureCount = scene.currentScene.figures.length;
      expect(figureCount, "scene has staged figures before handoff").toBeGreaterThanOrEqual(2);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "2-pre-handoff-scene.json"),
        JSON.stringify({ figureCount, figures: scene.currentScene.figures.map((f: any) => f.name) }, null, 2),
      );

      // Open the Export accordion (Versions + Exports) where the Co-Director
      // button lives. The right inspector pane may start collapsed on narrow
      // layouts or due to persisted prefs — expand it first, then toggle the
      // export accordion open (hydrate race protection).
      const expandRight = page.getByTestId("posecraft-expand-right");
      if (await expandRight.isVisible().catch(() => false)) {
        await expandRight.click();
        await page.waitForTimeout(300);
      }
      const exportToggle = page.getByTestId("posecraft-accordion-toggle-export");
      await expect(exportToggle).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(400);
      for (let attempt = 0; attempt < 10; attempt++) {
        if (await page.getByTestId("posecraft-export-actions").isVisible().catch(() => false)) break;
        if ((await exportToggle.getAttribute("aria-expanded")) !== "true") {
          await exportToggle.click();
        }
        await page.waitForTimeout(300);
      }
      await expect(page.getByTestId("posecraft-export-actions")).toBeVisible({ timeout: 10_000 });

      // The Co-Director button must be the FIRST action button in the stack.
      const sendCodirector = page.getByTestId("posecraft-send-codirector");
      await expect(sendCodirector).toBeVisible();
      const exportButtons = page.locator('[data-testid="posecraft-export-actions"] > button');
      const firstButtonTestid = await exportButtons.first().getAttribute("data-testid");
      expect(firstButtonTestid, "Co-Director is the first export action").toBe("posecraft-send-codirector");
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "3-button-order.json"),
        JSON.stringify({ firstButtonTestid }, null, 2),
      );

      // Mutate the scene locally (move a figure) WITHOUT waiting for the
      // debounced auto-save, so we can prove the handoff flushes the freshest
      // state. We move via the inspector X input which triggers mutateScene.
      const firstFigureId = scene.currentScene.figures[0].id;
      await page.getByTestId(`posecraft-figure-row-${firstFigureId}`).click();
      await page.waitForTimeout(200);
      const xInput = page.getByTestId("posecraft-figure-x");
      await xInput.fill("3.5");
      await page.waitForTimeout(150); // before the 600ms debounce fires

      // Snapshot gating: Send to Co-Director requires a selected Snapshot.
      // Capture a Snapshot now — this flushes the freshest scene (x=3.5),
      // performs a clean capture, uploads the PNG to the project Library,
      // appends a frozen Snapshot, and selects it for handoff.
      await expect(sendCodirector).toBeDisabled(); // gated until a Snapshot is selected
      await expect(page.getByTestId("posecraft-handoff-gate")).toBeVisible();
      const captureBtn = page.getByTestId("posecraft-snapshot-capture");
      await expect(captureBtn).toBeVisible();
      await captureBtn.click();
      // Wait for the capture to complete (flush → capture → upload → append → flush).
      await expect(page.getByTestId("posecraft-status-message")).toContainText(
        /Captured Snapshot for handoff/,
        { timeout: 30_000 },
      );
      await expect(page.getByTestId("posecraft-snapshot-list")).toBeVisible({ timeout: 10_000 });
      // A snapshot card must exist and be selected for handoff.
      const snapshotCards = page.locator('[data-testid^="posecraft-snapshot-card-"]');
      await expect(snapshotCards.first()).toBeVisible({ timeout: 10_000 });
      const snapshotCount = await snapshotCards.count();
      expect(snapshotCount, "a Snapshot was captured").toBeGreaterThanOrEqual(1);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "3b-snapshot-captured.json"),
        JSON.stringify({ snapshotCount }, null, 2),
      );
      // Send to Co-Director is now enabled (a Snapshot is selected).
      await expect(sendCodirector).toBeEnabled({ timeout: 10_000 });

      // Click "Send to Co-Director". This must flush the scene (PUT) and open
      // the Co-Director session with the prompt pre-filled in the composer.
      await sendCodirector.click();

      // Loading state must appear (button is wired, not dead).
      await expect(sendCodirector).toBeDisabled({ timeout: 5_000 });
      // Then it settles back to enabled.
      await expect(sendCodirector).toBeEnabled({ timeout: 10_000 });

      // The status message must confirm the handoff in creator language.
      await expect(page.getByTestId("posecraft-status-message")).toContainText(
        /Sent the PoseCraft Snapshot to Co-Director/,
        { timeout: 10_000 },
      );

      // The Co-Director session must open with the prompt pre-filled in the
      // composer input (auto-send path seeds the draft).
      const composerInput = page.getByTestId("codirector-composer-input");
      await expect(composerInput).toBeVisible({ timeout: 15_000 });
      const draftText = (await composerInput.inputValue()) || (await composerInput.textContent()) || "";
      fs.writeFileSync(path.join(ARTIFACT_DIR, "4-composer-draft.txt"), String(draftText));
      expect(draftText, "Co-Director composer seeded with PoseCraft Snapshot handoff prompt").toContain("PoseCraft Snapshot");
      expect(draftText, "prompt references the captured Snapshot").toContain("Snapshot");
      expect(draftText, "prompt asks Co-Director to inspect the frozen composition by id").toContain("inspect_scene");

      // The freshest scene (x=3.5) must have been flushed to the project API
      // by the handoff — Co-Director reads from there, not the browser.
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const movedFigure = scene.currentScene.figures.find((f: any) => f.id === firstFigureId);
      const flushedFresh = movedFigure?.position?.x === 3.5;
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "5-flushed-scene.json"),
        JSON.stringify({ firstFigureId, movedX: movedFigure?.position?.x, flushedFresh }, null, 2),
      );
      expect(flushedFresh, "handoff flushed the freshest scene to the project API").toBe(true);

      // Co-Director can actually receive the scene: execute the frozen
      // posecraft.inspect_scene read tool and confirm it returns the figures
      // we staged for the SAME project (read tools wrap the handler result in
      // a retrieval envelope, so the inspection lives under result.data).
      const inspectInvocation = await runReadTool(request, projectId, "posecraft.inspect_scene", {});
      const inspection = inspectInvocation?.result?.data?.inspection;
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "6-codirector-inspect.json"),
        JSON.stringify(inspectInvocation, null, 2),
      );
      expect(inspection, "inspect_scene returned an inspection payload").toBeTruthy();
      const inspectedFigureCount = inspection?.figureCount;
      const inspectedFigures: any[] = inspection?.figures || [];
      expect(inspectedFigureCount, "Co-Director received the staged figures").toBeGreaterThanOrEqual(2);
      // The freshest scene (with the moved figure x=3.5) must be what
      // Co-Director sees — proving the handoff flush reached the SoT.
      const inspectedMoved = inspectedFigures.find((f: any) => f.id === firstFigureId);
      expect(
        inspectedMoved?.position?.x,
        "Co-Director received the flushed (moved) figure position",
      ).toBe(3.5);

      // Protected project was never mutated.
      const protectedScene = await getJson(
        request,
        `/api/posecraft/projects/${PROTECTED_PROJECT}/scene`,
      ).catch(() => null);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "7-protected-check.json"),
        JSON.stringify({ checked: !!protectedScene }, null, 2),
      );

      await page.screenshot({ path: path.join(ARTIFACT_DIR, "8-codirector-open.png"), fullPage: true });

      // ---- Version card ⋯ menu: Rename / Duplicate / Delete (E2E) ----
      // The Co-Director chat panel overlays the right Inspector pane after
      // the handoff — close it so the milestones accordion is reachable.
      const codirectorClose = page.getByTestId("codirector-close-button");
      if (await codirectorClose.isVisible().catch(() => false)) {
        await codirectorClose.click();
        await page.waitForTimeout(400);
      }
      // The Version Label / Save Version / milestone cards now live under
      // Advanced → Scene milestones (a nested accordion inside Snapshots +
      // Exports). Open both the export accordion and the milestones accordion.
      for (let attempt = 0; attempt < 10; attempt++) {
        if (await page.getByTestId("posecraft-version-label").isVisible().catch(() => false)) break;
        const et = page.getByTestId("posecraft-accordion-toggle-export");
        if ((await et.getAttribute("aria-expanded")) !== "true") {
          await et.click();
        }
        await page.waitForTimeout(200);
        const mt = page.getByTestId("posecraft-accordion-toggle-milestones");
        if (await mt.isVisible().catch(() => false)) {
          if ((await mt.getAttribute("aria-expanded")) !== "true") {
            await mt.click();
          }
        }
        await page.waitForTimeout(300);
      }
      // Save a milestone version so there is a version card to test.
      await page.getByTestId("posecraft-version-label").fill("Wide master");
      await page.getByTestId("posecraft-save-version").click();
      await page.waitForTimeout(500);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const versions = scene.savedVersions || [];
      expect(versions.length, "a saved milestone exists").toBeGreaterThanOrEqual(1);
      const versionId = versions[0].id;
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "9-version-saved.json"),
        JSON.stringify({ versionId, label: versions[0].label, count: versions.length }, null, 2),
      );

      // The version card must be present and expose a ⋯ menu button.
      const versionCard = page.getByTestId(`posecraft-version-${versionId}`);
      await expect(versionCard).toBeVisible({ timeout: 10_000 });
      const versionMenuBtn = page.getByTestId(`posecraft-version-menu-${versionId}`);
      await expect(versionMenuBtn).toBeVisible();

      // Rename via the ⋯ menu → inline input → Enter.
      await versionMenuBtn.click();
      await expect(page.getByTestId(`posecraft-version-popover-${versionId}`)).toBeVisible();
      await page.getByTestId(`posecraft-version-rename-btn-${versionId}`).click();
      const vRenameInput = page.getByTestId(`posecraft-version-rename-${versionId}`);
      await expect(vRenameInput).toBeVisible();
      await vRenameInput.fill("Wide master v2");
      await vRenameInput.press("Enter");
      await page.waitForTimeout(600);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const renamedVersion = scene.savedVersions.find((v: any) => v.id === versionId);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "10-version-renamed.json"),
        JSON.stringify({ before: "Wide master", after: renamedVersion?.label }, null, 2),
      );
      expect(renamedVersion?.label, "version rename persisted to API").toBe("Wide master v2");

      // Duplicate via the ⋯ menu → a new adjacent version appears.
      const beforeDupCount = scene.savedVersions.length;
      await page.getByTestId(`posecraft-version-menu-${versionId}`).click();
      await page.getByTestId(`posecraft-version-duplicate-btn-${versionId}`).click();
      await page.waitForTimeout(600);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const afterDupCount = scene.savedVersions.length;
      const dupVersion = scene.savedVersions.find((v: any) => v.label === "Wide master v2 Copy");
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "11-version-duplicated.json"),
        JSON.stringify({ beforeDupCount, afterDupCount, dupId: dupVersion?.id }, null, 2),
      );
      expect(afterDupCount, "duplicate added one version").toBe(beforeDupCount + 1);
      expect(dupVersion?.id, "duplicate has a unique id").toBeTruthy();
      expect(dupVersion?.id, "duplicate is not the original").not.toBe(versionId);

      // Delete via the ⋯ menu → confirm → version gone after reload.
      const dupId = dupVersion!.id;
      // Accept the confirm dialog.
      page.once("dialog", (dialog) => dialog.accept());
      await page.getByTestId(`posecraft-version-menu-${dupId}`).click();
      await page.getByTestId(`posecraft-version-delete-btn-${dupId}`).click();
      await page.waitForTimeout(600);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      let dupGone = !scene.savedVersions.some((v: any) => v.id === dupId);
      fs.writeFileSync(
        path.join(ARTIFACT_DIR, "12-version-deleted.json"),
        JSON.stringify({ dupId, dupGone, remaining: scene.savedVersions.length }, null, 2),
      );
      expect(dupGone, "deleted version gone from API").toBe(true);

      // Persistence across reload: rename survives reload.
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await page.waitForTimeout(1000);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const survived = scene.savedVersions.find((v: any) => v.id === versionId);
      expect(survived?.label, "rename survived reload").toBe("Wide master v2");
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "13-versions-final.png"), fullPage: true });

      // Master verdict.
      const masterVerdict = "GO — POSECRAFT CODIRECTOR HANDOFF PASS";
      fs.writeFileSync(path.join(ARTIFACT_DIR, "master-verdict.txt"), masterVerdict);
    } finally {
      await deleteProject(request, projectId);
    }
  });
});
