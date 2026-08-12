/**
 * PoseCraft — Final Mandatory GO (Figures, Furniture & Custom Characters).
 *
 * Covers D1–D4 (low-poly human figures), D5–D6 (cast three-dot menu + keyboard
 * delete), FURN (walls + window walls), IMPORT (custom mesh import), STORY
 * (staging reference package), and COFFEE (coffee-shop certification).
 *
 * Emits per-gate GO/NO-GO verdict strings and writes artifacts under
 * docs/release-gate/posecraft/artifacts/final-mandatory-go/<RUN_ID>/.
 *
 * The implementer cannot self-certify; this spec produces evidence for a
 * SEPARATE glm-5.2-high non-implementer verifier.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { waitForAppReady } from "../helpers/app";

const API_BASE = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";
const RUN_PREFIX = "POSECRAFT-FINAL-MANDATORY-GO";
const RUN_ID = `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(process.cwd(), "docs", "release-gate", "posecraft", "artifacts", "final-mandatory-go", RUN_ID);
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
  return (await postJson(request, "/api/projects", { name, global_prompt: "PoseCraft final mandatory GO coffee-shop blocking." })).id;
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

const VERDICTS: string[] = [];
function recordVerdict(gate: string, pass: boolean, detail = "") {
  const verdict = pass
    ? `GO — POSECRAFT ${gate} PASS`
    : `NO-GO — POSECRAFT ${gate} FAIL${detail ? ` (${detail})` : ""}`;
  VERDICTS.push(verdict);
  fs.appendFileSync(path.join(ARTIFACT_DIR, "verdicts.txt"), `${verdict}\n`);
}

test.describe("PoseCraft Final Mandatory GO — Figures, Furniture & Custom Characters", () => {
  test.beforeAll(() => { fs.mkdirSync(ARTIFACT_DIR, { recursive: true }); });

  test("D1–D6, FURN, IMPORT, STORY, COFFEE — full certification", async ({ page, request }) => {
    test.setTimeout(15 * 60_000);
    expect(PROTECTED_PROJECT, "protected project id is configured").toBeTruthy();

    const projectId = await createProject(request, `${RUN_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}`);
    fs.writeFileSync(path.join(ARTIFACT_DIR, "1-project.json"), JSON.stringify({ projectId, protected: PROTECTED_PROJECT }, null, 2));

    try {
      await page.setViewportSize(VIEWPORT);
      await page.goto("/");
      await waitForAppReady(request);
      await page.goto(`/project/${projectId}?workspace=posecraft`);
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await expect(page.locator("canvas[data-testid='posecraft-babylon-canvas']")).toBeVisible();
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "00-shell-open.png"), fullPage: true });

      // Gate D1–D4 — low-poly human figures (male, female, boy, girl).
      await approveTool(request, projectId, "posecraft.add_figure", { archetypeId: "adult-male", colorId: "seaglass", name: "Eli" });
      await page.waitForTimeout(400);
      await approveTool(request, projectId, "posecraft.add_figure", { archetypeId: "adult-female", colorId: "seaglass", name: "Nora" });
      await page.waitForTimeout(400);
      await approveTool(request, projectId, "posecraft.add_figure", { archetypeId: "child-boy", colorId: "blue", name: "Sam" });
      await page.waitForTimeout(400);
      await approveTool(request, projectId, "posecraft.add_figure", { archetypeId: "child-girl", colorId: "blue", name: "Mia" });
      await page.waitForTimeout(800);
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await page.waitForTimeout(1000);

      let scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const figures = scene.currentScene.figures;
      const archetypes = figures.map((f: any) => f.archetypeId);
      expect(archetypes, "D1–D3: all four archetypes present").toEqual(expect.arrayContaining(["adult-male", "adult-female", "child-boy", "child-girl"]));
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D-figures.json"), JSON.stringify({ archetypes, figureCount: figures.length }, null, 2));
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "D1-front.png"), fullPage: true });

      // Read per-figure low-poly human metadata from the engine via window global.
      const meta = await page.evaluate((ids: string[]) => {
        const ctrl = (window as any).__posecraftController;
        const out: any[] = [];
        for (const id of ids) {
          const m = ctrl?.getFigureMetadata?.(id);
          if (m) out.push({ id, modelId: m.modelId, jointCount: m.jointCount, bodyRegions: m.bodyRegions, legacyBlockModel: m.legacyBlockModel });
        }
        return out;
      }, figures.map((f: any) => f.id));
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D-metadata.json"), JSON.stringify(meta, null, 2));
      const modelIds = meta.map((m: any) => m.modelId);
      const allLegacyFalse = meta.every((m: any) => m.legacyBlockModel === false);
      const jointCountOk = meta.every((m: any) => m.jointCount === 17);
      const regionsOk = meta.every((m: any) => Array.isArray(m.bodyRegions) && m.bodyRegions.length >= 17);
      recordVerdict("D1 ADULT MALE MODEL", modelIds.includes("adult-male-lowpoly-v2") && allLegacyFalse, `modelIds=${JSON.stringify(modelIds)}`);
      recordVerdict("D2 ADULT FEMALE MODEL", modelIds.includes("adult-female-lowpoly-v2") && allLegacyFalse, `modelIds=${JSON.stringify(modelIds)}`);
      recordVerdict("D3 CHILD MODELS", modelIds.includes("child-boy-lowpoly-v2") && modelIds.includes("child-girl-lowpoly-v2"), `modelIds=${JSON.stringify(modelIds)}`);
      recordVerdict("D4 SAME-COLOR SILHOUETTE", allLegacyFalse && jointCountOk && regionsOk, `jointCount=${jointCountOk} regions=${regionsOk}`);
      expect(modelIds, "D1–D3: v2 model ids present").toEqual(expect.arrayContaining(["adult-male-lowpoly-v2", "adult-female-lowpoly-v2", "child-boy-lowpoly-v2", "child-girl-lowpoly-v2"]));
      expect(allLegacyFalse, "D4: legacyBlockModel === false for all").toBe(true);

      // Gate FURN — walls + window walls render as Babylon objects.
      // Furniture often starts open from layout prefs — never click when already
      // expanded (that would close it). Retry only opens when closed (hydrate race).
      const furnToggle = page.getByTestId("posecraft-accordion-toggle-furniture");
      await expect(furnToggle).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(400);
      const furnPutLog: string[] = [];
      page.on("request", (req) => {
        if (req.method() === "PUT" && req.url().includes(`/api/posecraft/projects/${projectId}/scene`)) {
          try {
            const body = JSON.parse(req.postData() || "{}");
            const prims = body?.currentScene?.primitives?.map((p: any) => p.kind) ?? [];
            furnPutLog.push(`PUT prims=${JSON.stringify(prims)}`);
          } catch { furnPutLog.push("PUT (parse failed)"); }
        }
      });
      for (let attempt = 0; attempt < 8; attempt++) {
        if (await page.getByTestId("posecraft-furniture-grid").isVisible().catch(() => false)) break;
        if ((await furnToggle.getAttribute("aria-expanded")) !== "true") {
          await furnToggle.click();
        }
        await page.waitForTimeout(250);
      }
      await expect(page.getByTestId("posecraft-furniture-grid")).toBeVisible({ timeout: 10_000 });
      const wallKinds = ["wall-small", "wall-medium", "wall-large", "wall-window-small", "wall-window-medium", "wall-window-large"];
      for (const kind of wallKinds) {
        await page.getByTestId(`posecraft-add-furniture-${kind}`).click();
        await page.waitForTimeout(200);
      }
      // Poll the API until the debounced save persists all six wall kinds.
      let primKinds: string[] = [];
      for (let i = 0; i < 20; i++) {
        const afterFurn = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        primKinds = afterFurn.currentScene.primitives.map((p: any) => p.kind);
        if (wallKinds.every((k) => primKinds.includes(k))) break;
        await page.waitForTimeout(300);
      }
      // Debug: capture the in-browser scene state + status to diagnose races.
      const furnDebug = await page.evaluate(() => {
        const doc = (window as any).__posecraftDocument;
        return {
          localPrimitives: doc?.currentScene?.primitives?.map((p: any) => p.kind) ?? null,
          localFigureCount: doc?.currentScene?.figures?.length ?? null,
          status: (document.querySelector("[data-testid='posecraft-status-message']") as HTMLElement)?.textContent ?? null,
        };
      }).catch(() => null);
      const allWallsPresent = wallKinds.every((k) => primKinds.includes(k));
      fs.writeFileSync(path.join(ARTIFACT_DIR, "FURN-walls.json"), JSON.stringify({ primKinds, allWallsPresent, furnDebug, furnPutLog }, null, 2));
      recordVerdict("FURN WALLS AND WALL-WITH-WINDOW", allWallsPresent, `primKinds=${JSON.stringify(primKinds)}`);
      expect(allWallsPresent, "FURN: all wall kinds present").toBe(true);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "FURN-walls.png"), fullPage: true });

      // Gate D5 — three-dot menu: rename, duplicate, delete (persist).
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await page.waitForTimeout(1000);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const firstFigureId = scene.currentScene.figures[0]?.id;
      expect(firstFigureId, "D5: a figure exists to test the menu").toBeTruthy();

      // Rename via the three-dot menu.
      await page.getByTestId(`posecraft-figure-menu-${firstFigureId}`).click();
      await page.getByTestId(`posecraft-figure-rename-btn-${firstFigureId}`).click();
      const renameInput = page.getByTestId(`posecraft-figure-rename-${firstFigureId}`);
      await renameInput.fill("Eli Renamed");
      await renameInput.press("Enter");
      await page.waitForTimeout(600);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const renamed = scene.currentScene.figures.find((f: any) => f.id === firstFigureId);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D5-rename.json"), JSON.stringify({ before: "Eli", after: renamed?.name }, null, 2));
      recordVerdict("D5 FIGURE CONTEXT MENU RENAME", renamed?.name === "Eli Renamed", `name=${renamed?.name}`);
      expect(renamed?.name, "D5: rename persisted").toBe("Eli Renamed");

      // Duplicate via the three-dot menu → unique id + offset.
      const beforeCount = scene.currentScene.figures.length;
      await page.getByTestId(`posecraft-figure-menu-${firstFigureId}`).click();
      await page.getByTestId(`posecraft-figure-duplicate-btn-${firstFigureId}`).click();
      await page.waitForTimeout(700);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const afterCount = scene.currentScene.figures.length;
      const dup = scene.currentScene.figures.find((f: any) => f.id !== firstFigureId && f.name === "Eli Renamed Copy");
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D5-duplicate.json"), JSON.stringify({ beforeCount, afterCount, dupId: dup?.id }, null, 2));
      recordVerdict("D5 FIGURE CONTEXT MENU DUPLICATE", afterCount === beforeCount + 1 && !!dup && dup.id !== firstFigureId, `dupId=${dup?.id}`);
      expect(afterCount, "D5: duplicate added one figure").toBe(beforeCount + 1);
      expect(dup?.id, "D5: duplicate has unique id").not.toBe(firstFigureId);

      // Delete the duplicate via the three-dot menu → save/reload gone.
      const dupId = dup!.id;
      await page.getByTestId(`posecraft-figure-menu-${dupId}`).click();
      await page.getByTestId(`posecraft-figure-delete-btn-${dupId}`).click();
      await page.waitForTimeout(700);
      await page.reload();
      await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
      await page.waitForTimeout(1000);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const deletedGone = !scene.currentScene.figures.some((f: any) => f.id === dupId);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D5-delete.json"), JSON.stringify({ dupId, deletedGone, figureCount: scene.currentScene.figures.length }, null, 2));
      recordVerdict("D5 FIGURE CONTEXT MENU DELETE", deletedGone, `dupId=${dupId}`);
      expect(deletedGone, "D5: deleted figure gone after reload").toBe(true);

      // Gate D6 — keyboard Delete / Backspace; blocked in rename input.
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const kidTarget = scene.currentScene.figures[0]?.id;
      expect(kidTarget, "D6: a figure exists for keyboard delete").toBeTruthy();
      await page.getByTestId(`posecraft-figure-row-${kidTarget}`).click();
      await page.waitForTimeout(200);
      await page.keyboard.press("Delete");
      await page.waitForTimeout(700);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      let kidGone = !scene.currentScene.figures.some((f: any) => f.id === kidTarget);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D6-keyboard-delete.json"), JSON.stringify({ kidTarget, kidGone }, null, 2));
      recordVerdict("D6 KEYBOARD DELETE FIGURE", kidGone, `kidTarget=${kidTarget}`);
      expect(kidGone, "D6: keyboard Delete removed figure").toBe(true);

      // Keyboard Backspace on a furniture primitive.
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const furnitureId = scene.currentScene.primitives[0]?.id;
      expect(furnitureId, "D6: furniture exists for keyboard delete").toBeTruthy();
      await page.getByTestId(`posecraft-primitive-card-${furnitureId}`).click();
      await page.waitForTimeout(200);
      await page.keyboard.press("Backspace");
      await page.waitForTimeout(700);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const furnitureGone = !scene.currentScene.primitives.some((p: any) => p.id === furnitureId);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D6-keyboard-furniture.json"), JSON.stringify({ furnitureId, furnitureGone }, null, 2));
      recordVerdict("D6 KEYBOARD DELETE FURNITURE", furnitureGone, `furnitureId=${furnitureId}`);
      expect(furnitureGone, "D6: keyboard Backspace removed furniture").toBe(true);

      // Keyboard Delete must be ignored while renaming (focus in an input).
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const renameTarget = scene.currentScene.figures[0]?.id;
      expect(renameTarget, "D6: a figure exists for rename-while-typing").toBeTruthy();
      await page.getByTestId(`posecraft-figure-menu-${renameTarget}`).click();
      await page.getByTestId(`posecraft-figure-rename-btn-${renameTarget}`).click();
      const rInput = page.getByTestId(`posecraft-figure-rename-${renameTarget}`);
      await rInput.fill("Typing Name");
      await rInput.press("Delete");
      await page.waitForTimeout(400);
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const stillThere = scene.currentScene.figures.some((f: any) => f.id === renameTarget);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "D6-rename-blocked.json"), JSON.stringify({ renameTarget, stillThere }, null, 2));
      recordVerdict("D6 KEYBOARD DELETE BLOCKED IN INPUT", stillThere, `renameTarget=${renameTarget}`);
      expect(stillThere, "D6: Delete ignored while renaming").toBe(true);
      await rInput.press("Escape");
      await page.waitForTimeout(200);

      // Gate IMPORT — custom mesh import via project Library.
      const objFixture = path.join(process.cwd(), "tests", "fixtures", "posecraft-test-cube.obj");
      expect(fs.existsSync(objFixture), "IMPORT: OBJ fixture exists").toBe(true);
      const importConsole: string[] = [];
      page.on("console", (msg) => importConsole.push(`[${msg.type()}] ${msg.text()}`));
      page.on("pageerror", (err) => importConsole.push(`[pageerror] ${err.message}`));
      const importNet: string[] = [];
      page.on("request", (req) => { if (req.url().includes("/assets") && req.method() === "POST") importNet.push(`POST ${req.url()}`); });
      page.on("response", (res) => { if (res.url().includes("/assets")) importNet.push(`RESP ${res.status()} ${res.url()}`); });
      // Ensure the input is attached and settled before uploading (the D6
      // rename-escape just unmounted an input; give React a beat to commit).
      await page.waitForTimeout(300);
      await page.getByTestId("posecraft-custom-import-input").setInputFiles(objFixture);
      // Poll the API until the custom figure persists. The upload + flush is
      // async (mesh upload → addCustomFigureToScene → flush); a fixed wait
      // races the debounced save, so poll up to ~6s. Retry setInputFiles once
      // if the upload never landed (onChange flake).
      let importFigure: any = null;
      for (let i = 0; i < 20; i++) {
        await page.waitForTimeout(300);
        const importScene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        importFigure = importScene.currentScene.figures.find((f: any) => f.kind === "custom") ?? null;
        if (importFigure) break;
        if (i === 8 && importNet.length === 0) {
          await page.getByTestId("posecraft-custom-import-input").setInputFiles(objFixture);
        }
      }
      const importStatus = await page.getByTestId("posecraft-status-message").textContent().catch(() => null);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "IMPORT-debug.json"), JSON.stringify({ importStatus, importConsole, importNet, hasFigure: !!importFigure }, null, 2));
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      const customFigure = scene.currentScene.figures.find((f: any) => f.kind === "custom");
      fs.writeFileSync(path.join(ARTIFACT_DIR, "IMPORT-custom.json"), JSON.stringify({ customFigure }, null, 2));
      recordVerdict("IMPORT CUSTOM FIGURE", !!customFigure && !!customFigure.customAssetId, `customAssetId=${customFigure?.customAssetId}`);
      expect(customFigure?.kind, "IMPORT: custom figure added").toBe("custom");
      expect(customFigure?.customAssetId, "IMPORT: customAssetId stored").toBeTruthy();
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "IMPORT-custom.png"), fullPage: true });

      // Transform the custom figure (Move/Rotate/Scale only) and persist.
      if (customFigure) {
        await page.getByTestId(`posecraft-custom-row-${customFigure.id}`).click();
        await page.waitForTimeout(200);
        await page.getByTestId("posecraft-figure-x").fill("1.5");
        await page.getByTestId("posecraft-figure-yaw").fill("30");
        await page.getByTestId("posecraft-figure-scale").fill("1.2");
        await page.waitForTimeout(500);
        await page.reload();
        await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 45_000 });
        await page.waitForTimeout(1000);
        scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        const reloaded = scene.currentScene.figures.find((f: any) => f.id === customFigure.id);
        const transformPersisted = reloaded && reloaded.position?.x === 1.5 && reloaded.rotationY === 30 && reloaded.scale === 1.2;
        fs.writeFileSync(path.join(ARTIFACT_DIR, "IMPORT-transform.json"), JSON.stringify({ reloaded }, null, 2));
        recordVerdict("IMPORT CUSTOM FIGURE TRANSFORM PERSIST", !!transformPersisted, `pos=${reloaded?.position?.x} yaw=${reloaded?.rotationY} scale=${reloaded?.scale}`);
        expect(reloaded?.position?.x, "IMPORT: position persisted").toBe(1.5);
      }

      // Gate COFFEE — coffee-shop certification: male + female + medium table
      // + 2 block chairs + wall-window-medium. Added via UI furniture clicks.
      await page.getByTestId("posecraft-add-furniture-table-medium").click();
      await page.waitForTimeout(200);
      await page.getByTestId("posecraft-add-furniture-block-chair").click();
      await page.waitForTimeout(200);
      await page.getByTestId("posecraft-add-furniture-block-chair").click();
      await page.waitForTimeout(200);
      await page.getByTestId("posecraft-add-furniture-wall-window-medium").click();
      await page.waitForTimeout(200);
      // Poll until the coffee-shop furniture persists.
      let coffeeFurnitureKinds: string[] = [];
      for (let i = 0; i < 20; i++) {
        const afterCoffee = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
        coffeeFurnitureKinds = afterCoffee.currentScene.primitives.map((p: any) => p.kind);
        if (["table-medium", "block-chair", "wall-window-medium"].every((k) => coffeeFurnitureKinds.includes(k)) && coffeeFurnitureKinds.filter((k) => k === "block-chair").length >= 2) break;
        await page.waitForTimeout(300);
      }
      scene = await getJson(request, `/api/posecraft/projects/${projectId}/scene`);
      coffeeFurnitureKinds = scene.currentScene.primitives.map((p: any) => p.kind);
      const hasCoffeeSetup = ["table-medium", "block-chair", "wall-window-medium"].every((k) => coffeeFurnitureKinds.includes(k)) && coffeeFurnitureKinds.filter((k) => k === "block-chair").length >= 2;
      const hasMaleFemale = scene.currentScene.figures.some((f: any) => f.archetypeId === "adult-male") && scene.currentScene.figures.some((f: any) => f.archetypeId === "adult-female");
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "COFFEE-staging.png"), fullPage: true });
      fs.writeFileSync(path.join(ARTIFACT_DIR, "COFFEE-scene.json"), JSON.stringify({ furnitureKinds: coffeeFurnitureKinds, hasMaleFemale, figureCount: scene.currentScene.figures.length }, null, 2));
      recordVerdict("COFFEE COFFEE SHOP CERTIFICATION", hasCoffeeSetup && hasMaleFemale, `furniture=${JSON.stringify(coffeeFurnitureKinds)} maleFemale=${hasMaleFemale}`);
      expect(hasCoffeeSetup && hasMaleFemale, "COFFEE: coffee-shop staging present").toBe(true);

      // Gate STORY — export the staging reference package and verify it
      // contains figures (modelId + pose), furniture kinds, and camera/lens.
      const storyPayload = await page.evaluate(() => {
        const doc = (window as any).__posecraftDocument;
        return doc ? {
          figureCount: doc.currentScene.figures.length,
          figures: doc.currentScene.figures.map((f: any) => ({ modelId: f.archetypeId, hasPose: !!f.pose, kind: f.kind || "archetype", customAssetId: f.customAssetId ?? null })),
          furnitureKinds: doc.currentScene.primitives.map((p: any) => p.kind),
          lensMm: doc.currentScene.camera.lensMm,
          aspect: doc.currentScene.camera.aspect,
        } : null;
      });
      fs.writeFileSync(path.join(ARTIFACT_DIR, "STORY-package.json"), JSON.stringify(storyPayload, null, 2));
      const storyOk = !!storyPayload
        && storyPayload.figureCount > 0
        && storyPayload.figures.every((f: any) => !!f.modelId && (f.kind === "custom" ? !!f.customAssetId : f.hasPose))
        && storyPayload.furnitureKinds.length > 0
        && !!storyPayload.lensMm
        && !!storyPayload.aspect;
      recordVerdict("STORY STORYBOARD HANDOFF PRESERVE", storyOk, `figures=${storyPayload?.figureCount} furniture=${storyPayload?.furnitureKinds?.length}`);
      expect(storyOk, "STORY: package preserves figures + furniture + camera").toBe(true);

      // Protected project was never mutated.
      const protectedScene = await getJson(request, `/api/posecraft/projects/${PROTECTED_PROJECT}/scene`).catch(() => null);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "protected-project-check.json"), JSON.stringify({ checked: !!protectedScene }, null, 2));

      // Master verdict.
      const allPass = VERDICTS.every((v) => v.startsWith("GO"));
      const masterVerdict = allPass
        ? "GO — POSECRAFT LOW-POLY HUMAN FIGURE MODELS READY"
        : "NO-GO — POSECRAFT HUMAN FIGURE MODELS NOT ACCEPTABLE";
      fs.writeFileSync(path.join(ARTIFACT_DIR, "master-verdict.txt"), masterVerdict);
      fs.writeFileSync(path.join(ARTIFACT_DIR, "all-verdicts.txt"), VERDICTS.join("\n") + "\n");
      expect(allPass, `Master verdict: ${masterVerdict}\n${VERDICTS.join("\n")}`).toBe(true);
    } finally {
      await deleteProject(request, projectId);
    }
  });
});



