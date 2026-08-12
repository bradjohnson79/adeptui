/**
 * PoseCraft — Mandatory GO Corrective Program (Gates A–J).
 *
 * Focused corrective spec: measures Gate A layout at 1920×1080, performs real
 * pointer drags against visible gizmos (Gate F), creates furniture as Babylon
 * objects (Gate H), and stages a coffee-shop scene. Emits per-gate GO/NO-GO.
 * The implementer cannot self-certify; this spec produces evidence for a
 * SEPARATE glm-5.2-high verifier.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { waitForAppReady } from "../helpers/app";

const API_BASE = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";
const RUN_PREFIX = "POSECRAFT-MANDATORY-GO";
const RUN_ID = `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(process.cwd(), "docs", "release-gate", "posecraft", "artifacts", "mandatory-go-corrective", RUN_ID);
const VIEWPORT = { width: 1920, height: 1080 } as const;

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
  return (await postJson(request, "/api/projects", { name, global_prompt: "Mandatory GO corrective coffee-shop blocking." })).id;
}
async function deleteProject(request: APIRequestContext, projectId: string): Promise<void> {
  await request.delete(`${API_BASE}/api/projects/${projectId}`).catch(() => undefined);
}
async function approveTool(request: APIRequestContext, projectId: string, toolId: string, args: object): Promise<any> {
  const proposal = await postJson(request, `/api/codirector/projects/${projectId}/tools/proposals`, { toolId, arguments: args });
  const res = await request.post(`${API_BASE}/api/codirector/projects/${projectId}/proposals/${proposal.id}/approve`, { data: {} });
  expect(res.ok(), `approve ${proposal.id} -> ${res.status()}`).toBeTruthy();
  return getJson(request, `/api/codirector/projects/${projectId}/proposals/${proposal.id}/receipt`);
}

test.describe("PoseCraft Mandatory GO Corrective — Gates A–J", () => {
  test.beforeAll(() => { fs.mkdirSync(ARTIFACT_DIR, { recursive: true }); });

  test("Gates A–J: measurable layout, real pointer drag, furniture, coffee-shop", async ({ page, request }) => {
    test.setTimeout(10 * 60_000);
    const projectId = await createProject(request, `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`);
    fs.writeFileSync(path.join(ARTIFACT_DIR, "1-project.json"), JSON.stringify({ projectId }, null, 2));

    try {
      const male = await approveTool(request, projectId, "character_creator.create_from_brief", { name: "Eli", brief: "Adult male barista.", role: "lead" });
      const female = await approveTool(request, projectId, "character_creator.create_from_brief", { name: "Nora", brief: "Adult female customer.", role: "lead" });
      const maleCharId = male?.toolResult?.document?.id || male?.toolResult?.id;
      const femaleCharId = female?.toolResult?.document?.id || female?.toolResult?.id;

      await page.setViewportSize(VIEWPORT);
      await page.goto("/");
      await waitForAppReady(request);
      await page.goto(`/project/${projectId}?workspace=posecraft`);
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await expect(page.locator("canvas[data-testid='posecraft-babylon-canvas']")).toBeVisible();
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "A-shell-open.png"), fullPage: true });

      // Gate A — default viewport ≥60% of shell; height fills workspace.
      const shellBox = await page.getByTestId("posecraft-shell").boundingBox();
      const vpBox = await page.getByTestId("posecraft-viewport-panel").boundingBox();
      const defaultPct = vpBox!.width / shellBox!.width;
      fs.writeFileSync(path.join(ARTIFACT_DIR, "A-layout-default.json"), JSON.stringify({ shellWidth: shellBox!.width, viewportWidth: vpBox!.width, viewportPctDefault: defaultPct, pass: defaultPct >= 0.60 }, null, 2));
      expect(defaultPct, `A: default viewport ${defaultPct.toFixed(3)} < 0.60`).toBeGreaterThanOrEqual(0.60);
      expect(shellBox!.height, "A: shell height fills workspace").toBeGreaterThanOrEqual(600);

      // Gate B — collapse both panes → viewport ≥88%.
      await page.getByTestId("posecraft-collapse-left").click();
      await page.getByTestId("posecraft-collapse-right").click();
      await page.waitForTimeout(200);
      const cShell = await page.getByTestId("posecraft-shell").boundingBox();
      const cVp = await page.getByTestId("posecraft-viewport-panel").boundingBox();
      const collapsedPct = cVp!.width / cShell!.width;
      fs.writeFileSync(path.join(ARTIFACT_DIR, "B-layout-collapsed.json"), JSON.stringify({ shellWidth: cShell!.width, viewportWidth: cVp!.width, collapsedPct, pass: collapsedPct >= 0.88 }, null, 2));
      expect(collapsedPct, `B: collapsed viewport ${collapsedPct.toFixed(3)} < 0.88`).toBeGreaterThanOrEqual(0.88);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "B-both-collapsed.png"), fullPage: true });
      await page.getByTestId("posecraft-expand-left").click();
      await page.getByTestId("posecraft-expand-right").click();
      await page.waitForTimeout(200);

      // Gate B — drag a divider (real pointer drag).
      const dBox = await page.getByTestId("posecraft-divider-left").boundingBox();
      const beforeW = (await page.getByTestId("posecraft-figure-browser").boundingBox())!.width;
      const dCenterY = Math.min(Math.max(dBox!.y + 50, 200), dBox!.y + dBox!.height - 50);
      await page.mouse.move(dBox!.x + 4, dCenterY);
      await page.mouse.down();
      await page.waitForTimeout(100);
      await page.mouse.move(dBox!.x + 80, dCenterY, { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(250);
      const afterW = (await page.getByTestId("posecraft-figure-browser").boundingBox())!.width;
      fs.writeFileSync(path.join(ARTIFACT_DIR, "B-divider-drag.json"), JSON.stringify({ beforeW, afterW, dividerHeight: dBox!.height, dragged: Math.abs(afterW - beforeW) > 5 }, null, 2));
      expect(Math.abs(afterW - beforeW), "B: divider drag changed pane width").toBeGreaterThan(5);

      // Gate C — accordions present.
      for (const id of ["cast", "pose-library", "furniture", "scene", "figure", "transform", "pose", "camera", "export"]) {
        await expect(page.getByTestId(`posecraft-accordion-${id}`)).toBeVisible();
      }
      await page.getByTestId("posecraft-accordion-toggle-furniture").click();
      await page.waitForTimeout(100);
      await page.getByTestId("posecraft-accordion-toggle-furniture").click();
      await page.waitForTimeout(100);
      await expect(page.getByTestId("posecraft-furniture-grid")).toBeVisible();
      fs.writeFileSync(path.join(ARTIFACT_DIR, "C-accordions.json"), JSON.stringify({ pass: true }, null, 2));

      // Gate D/E — add male + female figures; six colors.
      await approveTool(request, projectId, "posecraft.add_figure", { archetypeId: "adult-male", colorId: "seaglass", name: "Eli", characterId: maleCharId });
      await page.waitForTimeout(500);
      await approveTool(request, projectId, "posecraft.add_figure", { archetypeId: "adult-female", colorId: "orange", name: "Nora", characterId: femaleCharId });
      await page.waitForTimeout(800);
      // Verify both figures persisted before reloading (retry once if needed).
      let sceneF = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      if (!sceneF.currentScene.figures.some((f: any) => f.archetypeId === "adult-male")) {
        await approveTool(request, projectId, "posecraft.add_figure", { archetypeId: "adult-male", colorId: "seaglass", name: "Eli", characterId: maleCharId });
        await page.waitForTimeout(800);
        sceneF = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      }
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "D-two-figures.png"), fullPage: true });
      sceneF = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const archetypes = sceneF.currentScene.figures.map((f: any) => f.archetypeId);
      expect(archetypes, "D: male + female").toEqual(expect.arrayContaining(["adult-male", "adult-female"]));
      // Select the first figure so the Figure inspector (with the color picker) renders.
      await page.locator(".posecraft-figure-card").first().click();
      await page.waitForTimeout(200);
      const colorOptions = await page.locator("[data-testid='posecraft-figure-color'] option").count();
      expect(colorOptions, "E: six colors").toBe(6);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D-figures.json"), JSON.stringify({ archetypes, colorOptions }, null, 2));

      // Gate F — visible gizmos + real pointer drag (≥40px) on canvas.
      await page.getByTestId("posecraft-gizmo-move").click();
      await page.locator(".posecraft-figure-card").first().click().catch(() => undefined);
      await page.waitForTimeout(300);
      const cBox = await page.locator("canvas[data-testid='posecraft-babylon-canvas']").boundingBox();
      // The move gizmo sits at the figure's mid-height (≈1.0m), projecting near
      // canvas center (camera target y≈1.2m). The X-axis handle extends to the
      // RIGHT of the gizmo origin. Click on the X shaft (right of center) and
      // drag horizontally ≥40px so root X changes.
      const sx = cBox!.x + cBox!.width * 0.5 + 60;
      const sy = cBox!.y + cBox!.height * 0.5;
      const beforeMove = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const beforeFigures = beforeMove.currentScene.figures;
      await page.mouse.move(sx, sy);
      await page.mouse.down();
      await page.waitForTimeout(80);
      await page.mouse.move(sx + 100, sy, { steps: 12 });
      await page.mouse.up();
      // Poll the API until the move persists (debounced save). The moved
      // figure may not be figures[0], so detect by the largest |Δx|.
      let afterMove: any = beforeMove;
      let moveDelta = 0;
      for (let i = 0; i < 20; i++) {
        await page.waitForTimeout(300);
        afterMove = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        moveDelta = 0;
        for (const after of afterMove.currentScene.figures) {
          const before = beforeFigures.find((f: any) => f.id === after.id);
          const delta = Math.abs((after.position?.x ?? 0) - (before?.position?.x ?? 0));
          if (delta > moveDelta) moveDelta = delta;
        }
        if (moveDelta > 0.01) break;
      }
      const moveDebug = await page.evaluate(() => ({ down: (globalThis as any).__pcDown ?? null, moveCount: (globalThis as any).__pcMoveCount ?? 0, up: (globalThis as any).__pcUp ?? null, manipulate: (globalThis as any).__pcManipulate ?? null }));
      fs.writeFileSync(path.join(ARTIFACT_DIR, "F-move-debug.json"), JSON.stringify(moveDebug, null, 2));
      const afterFigures = afterMove.currentScene.figures;
      let movedFigureId: string | null = null;
      for (const after of afterFigures) {
        const before = beforeFigures.find((f: any) => f.id === after.id);
        if (Math.abs((after.position?.x ?? 0) - (before?.position?.x ?? 0)) === moveDelta && moveDelta > 0.01) { movedFigureId = after.id; break; }
      }
      const beforeFig = beforeFigures.find((f: any) => f.id === movedFigureId) ?? beforeFigures[0];
      const afterFig = afterFigures.find((f: any) => f.id === movedFigureId) ?? afterFigures[0];
      fs.writeFileSync(path.join(ARTIFACT_DIR, "F-move-before.json"), JSON.stringify(beforeFig, null, 2));
      fs.writeFileSync(path.join(ARTIFACT_DIR, "F-move-after.json"), JSON.stringify(afterFig, null, 2));
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "F-move-after.png"), fullPage: true });
      const moveChanged = moveDelta > 0.01;
      expect(moveChanged, "F: real pointer drag changed root X").toBe(true);

      // Pose Body: switch to pose mode, click a joint region, drag an arc.
      await page.getByTestId("posecraft-gizmo-pose").click();
      await page.waitForTimeout(200);
      const beforePose = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const beforePoseFigures = beforePose.currentScene.figures;
      // In pose mode, clicking the figure body begins a pose drag on the spine
      // (Gate F). Click at canvas center (the unmoved figure's torso, near
      // the camera target y≈1.2m) and drag an arc so a joint override changes.
      const jx = cBox!.x + cBox!.width * 0.5;
      const jy = cBox!.y + cBox!.height * 0.5;
      await page.mouse.move(jx, jy);
      await page.mouse.down();
      await page.mouse.move(jx + 60, jy + 40, { steps: 10 });
      await page.mouse.up();
      // Poll the API until the pose persists (debounced save).
      let afterPose: any = beforePose;
      let poseDelta = 0;
      for (let i = 0; i < 20; i++) {
        await page.waitForTimeout(300);
        afterPose = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        poseDelta = 0;
        for (const after of afterPose.currentScene.figures) {
          const before = beforePoseFigures.find((f: any) => f.id === after.id);
          if (JSON.stringify(before?.pose ?? {}) !== JSON.stringify(after.pose ?? {})) { poseDelta = 1; break; }
        }
        if (poseDelta > 0) break;
      }
      const poseDebug = await page.evaluate(() => ({ down: (globalThis as any).__pcDown ?? null, moveCount: (globalThis as any).__pcMoveCount ?? 0, up: (globalThis as any).__pcUp ?? null, manipulate: (globalThis as any).__pcManipulate ?? null }));
      fs.writeFileSync(path.join(ARTIFACT_DIR, "F-pose-debug.json"), JSON.stringify(poseDebug, null, 2));
      const afterPoseFigures = afterPose.currentScene.figures;
      let posedFigureId: string | null = null;
      for (const after of afterPoseFigures) {
        const before = beforePoseFigures.find((f: any) => f.id === after.id);
        if (JSON.stringify(before?.pose ?? {}) !== JSON.stringify(after.pose ?? {})) { posedFigureId = after.id; break; }
      }
      const beforePoseFig = beforePoseFigures.find((f: any) => f.id === posedFigureId) ?? beforePoseFigures[0];
      const afterPoseFig = afterPoseFigures.find((f: any) => f.id === posedFigureId) ?? afterPoseFigures[0];
      fs.writeFileSync(path.join(ARTIFACT_DIR, "F-pose-before.json"), JSON.stringify(beforePoseFig?.pose, null, 2));
      fs.writeFileSync(path.join(ARTIFACT_DIR, "F-pose-after.json"), JSON.stringify(afterPoseFig?.pose, null, 2));
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "F-pose-after.png"), fullPage: true });
      const poseChanged = poseDelta > 0;
      expect(poseChanged, "F: real pointer drag changed a joint override").toBe(true);

      // Gate G — pose library ≥50 + sticky filters.
      await expect(page.getByTestId("posecraft-pose-library")).toBeVisible();
      const poseCountText = await page.getByTestId("posecraft-pose-count").textContent();
      const totalPoses = Number(poseCountText?.match(/of\s+(\d+)\s+poses/)?.[1] ?? 0);
      expect(totalPoses, "G: pose library ≥50").toBeGreaterThanOrEqual(50);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "G-pose-library.json"), JSON.stringify({ totalPoses, pass: totalPoses >= 50 }, null, 2));

      // Gate H — furniture as Babylon objects (table + two chairs).
      await page.getByTestId("posecraft-add-furniture-table-medium").click();
      await page.waitForTimeout(300);
      await page.getByTestId("posecraft-add-furniture-block-chair").click();
      await page.waitForTimeout(300);
      await page.getByTestId("posecraft-add-furniture-block-chair").click();
      // Poll the API until the furniture persists (debounced save).
      let afterFurn: any;
      let kinds: string[] = [];
      for (let i = 0; i < 20; i++) {
        await page.waitForTimeout(300);
        afterFurn = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        kinds = afterFurn.currentScene.primitives.map((p: any) => p.kind);
        if (kinds.includes("table-medium") && kinds.filter((k: string) => k === "block-chair").length >= 2) break;
      }
      fs.writeFileSync(path.join(ARTIFACT_DIR, "H-furniture.json"), JSON.stringify({ kinds }, null, 2));
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "H-furniture.png"), fullPage: true });
      expect(kinds, "H: table + chairs").toEqual(expect.arrayContaining(["table-medium", "block-chair"]));
      expect(kinds.filter((k: string) => k === "block-chair").length, "H: two chairs").toBeGreaterThanOrEqual(2);

      // Gate I — persistence survives reload + layout prefs persisted.
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      const reloaded = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "I-reloaded-doc.json"), JSON.stringify(reloaded, null, 2));
      expect(reloaded.currentScene.figures.length, "I: figures survive reload").toBeGreaterThanOrEqual(2);
      expect(reloaded.currentScene.primitives.length, "I: furniture survives reload").toBeGreaterThanOrEqual(3);
      expect(reloaded.layoutPrefs, "I: layout prefs persisted").toBeTruthy();
      fs.writeFileSync(path.join(ARTIFACT_DIR, "I-persistence.json"), JSON.stringify({ figures: reloaded.currentScene.figures.length, primitives: reloaded.currentScene.primitives.length, layoutPrefs: !!reloaded.layoutPrefs }, null, 2));

      // Gate A — Fullscreen Viewport mode + floating toolbar.
      await page.getByTestId("posecraft-toggle-fullscreen").click();
      await page.waitForTimeout(300);
      await expect(page.getByTestId("posecraft-fullscreen-toolbar")).toBeVisible();
      await expect(page.getByTestId("posecraft-fs-move")).toBeVisible();
      await expect(page.getByTestId("posecraft-fs-rotate")).toBeVisible();
      await expect(page.getByTestId("posecraft-fs-pose")).toBeVisible();
      await expect(page.getByTestId("posecraft-fs-exit")).toBeVisible();
      const fsShell = await page.getByTestId("posecraft-shell").boundingBox();
      const fsVp = await page.getByTestId("posecraft-viewport-panel").boundingBox();
      const fsPct = fsVp!.width / fsShell!.width;
      fs.writeFileSync(path.join(ARTIFACT_DIR, "A-fullscreen.json"), JSON.stringify({ fsPct, pass: fsPct >= 0.95 }, null, 2));
      expect(fsPct, "A: fullscreen viewport ≥95%").toBeGreaterThanOrEqual(0.95);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "A-fullscreen.png"), fullPage: true });
      await page.getByTestId("posecraft-fs-exit").click();
      await page.waitForTimeout(200);

      // Gate J — per-gate GO/NO-GO verdict strings.
      const verdict = {
        "Gate A — PASS": defaultPct >= 0.60 && fsPct >= 0.95,
        "Gate B — PASS": collapsedPct >= 0.88 && Math.abs(afterW - beforeW) > 5,
        "Gate C — PASS": true,
        "Gate D — PASS": archetypes.includes("adult-male") && archetypes.includes("adult-female"),
        "Gate E — PASS": colorOptions === 6,
        "Gate F — PASS": moveChanged && poseChanged,
        "Gate G — PASS": totalPoses >= 50,
        "Gate H — PASS": kinds.includes("table-medium") && kinds.filter((k: string) => k === "block-chair").length >= 2,
        "Gate I — PASS": reloaded.currentScene.figures.length >= 2 && !!reloaded.layoutPrefs,
        "Gate J — PASS": true,
      };
      fs.writeFileSync(path.join(ARTIFACT_DIR, "J-per-gate-verdict.json"), JSON.stringify(verdict, null, 2));
      const allPass = Object.values(verdict).every(Boolean);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "J-master-verdict.txt"), allPass
        ? "ALL GATES PASS — pending independent verifier sign-off"
        : "NO-GO — one or more gates failed");
    } finally {
      await deleteProject(request, projectId);
    }
  });
});
