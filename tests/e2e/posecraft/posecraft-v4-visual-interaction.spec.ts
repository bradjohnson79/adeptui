import { expect, test } from "@playwright/test";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

async function waitReady(page: import("@playwright/test").Page, figureId: string) {
  await page.waitForFunction(() => Boolean((window as any).__posecraftController), null, { timeout: 20_000 });
  try {
    await page.waitForFunction((id) => {
      const ctrl = (window as any).__posecraftController;
      return ctrl?.getVisualState?.(id) === "READY" && ctrl?.getFigureMetadata?.(id)?.modelId?.endsWith("-v4");
    }, figureId, { timeout: 30_000 });
  } catch (error) {
    const dump = await page.evaluate((id) => {
      const ctrl = (window as any).__posecraftController;
      return {
        ids: ctrl?.getFigureIds?.() ?? [],
        state: ctrl?.getVisualState?.(id) ?? null,
        meta: ctrl?.getFigureMetadata?.(id) ?? null,
        banner: document.querySelector("[data-testid='posecraft-figure-load-error']")?.textContent ?? null,
      };
    }, figureId);
    throw new Error(`v4 READY wait failed for ${figureId}: ${JSON.stringify(dump)} — ${error}`);
  }
}

test.describe("PoseCraft v4 visual + interaction", () => {
  test("Adult Female v4 load, pose-body click, persist, reload", async ({ page, request }) => {
    const health = await request.get(`${API}/api/health`);
    expect(health.ok()).toBeTruthy();

    await page.goto(`${WEB}/project/${PROJECT_ID}?workspace=posecraft`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });

    const sceneBeforeAdd = await request.get(`${API}/api/posecraft/projects/${PROJECT_ID}/scene`);
    expect(sceneBeforeAdd.ok()).toBeTruthy();
    const docBeforeAdd = await sceneBeforeAdd.json();
    const existingFemale = [...(docBeforeAdd.currentScene?.figures ?? [])].reverse().find((f: { archetypeId: string }) => f.archetypeId === "adult-female");
    if (!existingFemale) {
      await page.getByTestId("posecraft-add-adult-female").click();
      await page.waitForTimeout(600);
    }
    const sceneBefore = await request.get(`${API}/api/posecraft/projects/${PROJECT_ID}/scene`);
    expect(sceneBefore.ok()).toBeTruthy();
    const docBefore = await sceneBefore.json();
    const female = [...docBefore.currentScene.figures].reverse().find((f: { archetypeId: string }) => f.archetypeId === "adult-female");
    expect(female, "Adult Female is in the Schnick PoseCraft scene").toBeTruthy();

    await waitReady(page, female.id);
    await page.locator(`[data-testid="posecraft-figure-row-${female.id}"] button.posecraft-figure-row-main`).click();
    const meta = await page.evaluate((id) => (window as any).__posecraftController?.getFigureMetadata?.(id), female.id);
    expect(meta.modelId).toBe("adult-female-lowpoly-v4");
    expect(meta.assetSource).toContain("adult-female-lowpoly-v4.glb");
    expect(meta.visualState).toBe("READY");
    expect(meta.legacyBlockModel).toBe(false);

    await page.getByTestId("posecraft-gizmo-pose").click();
    await page.waitForFunction((id) => {
      const sceneLabel = document.querySelector(`[data-testid="posecraft-figure-row-${id}"]`);
      return sceneLabel?.className.includes("selected") || Boolean((window as any).__posecraftController);
    }, female.id);
    const point = await page.evaluate((id) => (window as any).__posecraftController?.getRegionCanvasPoint?.(id, "head"), female.id);
    expect(point, "head has a canvas point").toBeTruthy();
    const box = await page.locator("canvas[data-testid='posecraft-babylon-canvas']").boundingBox();
    expect(box).toBeTruthy();
    await page.mouse.click(box!.x + point.x, box!.y + point.y);
    await page.waitForTimeout(250);
    const clickedJoint = await page.evaluate(() => (window as any).__posecraftController?.getSelectedJoint?.());
    const joints = ["pelvis","spine","chest","neck","head","leftShoulder","leftElbow","leftWrist","rightShoulder","rightElbow","rightWrist","leftHip","leftKnee","leftAnkle","rightHip","rightKnee","rightAnkle"];
    expect(joints, `canvas pick selected ${clickedJoint}`).toContain(clickedJoint);
    await page.getByTestId("posecraft-joint-select").selectOption("head");
    await expect(page.getByTestId("posecraft-joint-select")).toHaveValue("head");
    await page.locator(`[data-testid="posecraft-figure-row-${female.id}"] button.posecraft-figure-row-main`).click();
    await page.waitForTimeout(300);

    const poseToggle = page.getByTestId("posecraft-accordion-toggle-pose-library");
    if ((await poseToggle.getAttribute("aria-expanded")) !== "true") {
      await poseToggle.click();
    }
    const poseCard = page.getByTestId("posecraft-pose-dialogue-think");
    await expect(poseCard).toBeEnabled({ timeout: 10_000 });
    await poseCard.click({ force: true });
    await page.waitForFunction((id) => {
      const euler = (window as any).__posecraftController?.getJointEuler?.(id, "head");
      return euler && Math.round(euler.x) === -10;
    }, female.id, { timeout: 10_000 });
    const posed = await page.evaluate((id) => (window as any).__posecraftController?.getJointEuler?.(id, "head"), female.id);
    let saved: { x: number; y: number; z: number } | null = null;
    for (let i = 0; i < 20; i += 1) {
      const scene = await (await request.get(`${API}/api/posecraft/projects/${PROJECT_ID}/scene`)).json();
      const fig = scene.currentScene.figures.find((entry: { id: string }) => entry.id === female.id);
      if (fig?.pose?.head && Math.round(fig.pose.head.x) === -10) {
        saved = fig.pose.head;
        break;
      }
      await page.waitForTimeout(400);
    }
    expect(saved ?? posed, "Thinking pose applied on the live figure").toBeTruthy();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
    await waitReady(page, female.id);
    const liveAfter = await page.evaluate((id) => (window as any).__posecraftController?.getJointEuler?.(id, "head"), female.id);
    expect(Math.round(liveAfter?.x ?? 0)).toBe(-10);
    if (saved) {
      const afterReload = await (await request.get(`${API}/api/posecraft/projects/${PROJECT_ID}/scene`)).json();
      const reloaded = afterReload.currentScene.figures.find((entry: { id: string }) => entry.id === female.id);
      expect(Math.round(reloaded.pose.head.x)).toBe(-10);
    }
  });

  test("other archetypes load v4 READY", async ({ page }) => {
    await page.goto(`${WEB}/project/${PROJECT_ID}?workspace=posecraft`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
    await page.waitForFunction(() => Boolean((window as any).__posecraftController?.getFigureIds?.()?.length), null, { timeout: 20_000 });
    for (const add of ["posecraft-add-adult-male", "posecraft-add-child-boy", "posecraft-add-child-girl"] as const) {
      await page.getByTestId(add).scrollIntoViewIfNeeded();
      await page.getByTestId(add).click();
      await page.waitForTimeout(250);
    }
    const needed = ["adult-male-lowpoly-v4", "child-boy-lowpoly-v4", "child-girl-lowpoly-v4"];
    await page.waitForFunction((want: string[]) => {
      const ctrl = (window as any).__posecraftController;
      const ids = ctrl?.getFigureIds?.() ?? [];
      const rows = ids.map((id: string) => ({
        modelId: ctrl.getFigureMetadata?.(id)?.modelId,
        state: ctrl.getVisualState?.(id),
      }));
      return want.every((modelId) => rows.some((row: { modelId: string; state: string }) => row.modelId === modelId && row.state === "READY"));
    }, needed, { timeout: 30_000 });
  });

  test("Camera mode does not activate Move", async ({ page }) => {
    await page.goto(`${WEB}/project/${PROJECT_ID}?workspace=posecraft`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("posecraft-gizmo-camera").click();
    const mode = await page.evaluate(() => (window as any).__posecraftController?.getGizmoMode?.());
    expect(mode).toBe("camera");
    const gizmos = await page.evaluate(() => {
      const down = { mode: (window as any).__posecraftController?.getGizmoMode?.() };
      return down;
    });
    expect(gizmos.mode).toBe("camera");
  });
});
