/**
 * PoseCraft Visual Truth Law — Section 36 / 37 certification matrix.
 *
 * An action is NOT certified because JSON changed. Every manipulation must
 * prove: user action → joint state change AND visible GLB geometry change
 * → save → reload → geometry reconstructs.
 *
 * Runs against live Beta (8760 / 8758) on the Schnick Coffee project.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

const SEVEN_REGIONS = [
  ["head", "head"],
  ["leftUpperArm", "leftShoulder"],
  ["leftLowerArm", "leftElbow"],
  ["leftHand", "leftWrist"],
  ["leftUpperLeg", "leftHip"],
  ["leftLowerLeg", "leftKnee"],
  ["leftFoot", "leftAnkle"],
] as const;

type Vec3 = { x: number; y: number; z: number };

function dist(a: Vec3, b: Vec3): number {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

function byteDiff(a: Buffer, b: Buffer): number {
  const n = Math.min(a.length, b.length);
  let diff = 0;
  for (let i = 0; i < n; i += 1) if (a[i] !== b[i]) diff += 1;
  return diff + Math.abs(a.length - b.length);
}

async function waitReady(page: Page, figureId: string) {
  await page.waitForFunction(() => Boolean((window as any).__posecraftController), null, { timeout: 20_000 });
  await page.waitForFunction(
    (id) => {
      const ctrl = (window as any).__posecraftController;
      return ctrl?.getVisualState?.(id) === "READY" && String(ctrl?.getFigureMetadata?.(id)?.modelId || "").endsWith("-v4");
    },
    figureId,
    { timeout: 30_000 },
  );
}

async function openPoseCraft(page: Page) {
  await page.goto(`${WEB}/project/${PROJECT_ID}?workspace=posecraft`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("canvas[data-testid='posecraft-babylon-canvas']")).toBeVisible({ timeout: 30_000 });
}

async function latestFigure(request: APIRequestContext, archetypeId: string) {
  const scene = await (await request.get(`${API}/api/posecraft/projects/${PROJECT_ID}/scene`)).json();
  return [...(scene.currentScene?.figures ?? [])].reverse().find((f: { archetypeId: string }) => f.archetypeId === archetypeId);
}

async function ensureArchetype(page: Page, request: APIRequestContext, archetypeId: string) {
  const existing = await latestFigure(request, archetypeId);
  if (existing) return existing;
  await page.getByTestId(`posecraft-add-${archetypeId}`).click();
  await page.waitForTimeout(700);
  const added = await latestFigure(request, archetypeId);
  expect(added, `${archetypeId} is on the stage`).toBeTruthy();
  return added;
}

async function selectFigure(page: Page, figureId: string) {
  await page.locator(`[data-testid="posecraft-figure-row-${figureId}"] button.posecraft-figure-row-main`).click();
  await page.getByTestId("posecraft-gizmo-pose").click();
  await page.waitForTimeout(200);
}

async function captureEvidence(page: Page, figureId: string, regions: string[]) {
  const state = await page.evaluate(
    ({ id, regs }) => {
      const ctrl = (window as any).__posecraftController;
      const joints: Record<string, Vec3 | null> = {};
      const centers: Record<string, Vec3 | null> = {};
      for (const joint of [
        "head",
        "leftShoulder",
        "leftElbow",
        "leftWrist",
        "rightShoulder",
        "rightElbow",
        "rightWrist",
        "leftHip",
        "leftKnee",
        "chest",
      ]) {
        joints[joint] = ctrl?.getJointEuler?.(id, joint) ?? null;
      }
      for (const region of regs) {
        centers[region] = ctrl?.getRegionWorldCenter?.(id, region) ?? null;
      }
      return { joints, centers, selected: ctrl?.getSelectedJoint?.() ?? null };
    },
    { id: figureId, regs: regions },
  );
  const pixels = await page.locator("canvas[data-testid='posecraft-babylon-canvas']").screenshot();
  return { ...state, pixels };
}

const REGION_JOINT: Record<string, string> = {
  head: "head",
  leftUpperArm: "leftShoulder",
  leftLowerArm: "leftElbow",
  leftHand: "leftWrist",
  leftUpperLeg: "leftHip",
  leftLowerLeg: "leftKnee",
  leftFoot: "leftAnkle",
};

async function frameFigure(page: Page, figureId: string) {
  await page.evaluate((id) => {
    const ctrl = (window as any).__posecraftController;
    const cam = ctrl?.camera || ctrl?.scene?.activeCamera;
    const pos = ctrl?.getJointWorldPosition?.(id, "chest");
    if (!cam || !pos) return;
    cam.target.x = pos.x;
    cam.target.y = pos.y;
    cam.target.z = pos.z;
    cam.alpha = Math.PI / 2;
    cam.beta = 1.2;
    cam.radius = 2.8;
    ctrl?.scene?.render?.();
  }, figureId);
  await page.waitForTimeout(350);
}

async function clickRegion(page: Page, figureId: string, region: string) {
  const joint = REGION_JOINT[region] || region;
  const point = await page.evaluate(
    ({ id, region: r, joint: j }) => {
      const ctrl = (window as any).__posecraftController;
      ctrl?.scene?.render?.();
      const regionPt = ctrl?.getRegionCanvasPoint?.(id, r);
      const jointPt = ctrl?.getJointCanvasPoint?.(id, j);
      if (regionPt && jointPt) {
        return {
          x: regionPt.x * 0.35 + jointPt.x * 0.65,
          y: regionPt.y * 0.35 + jointPt.y * 0.65,
        };
      }
      return jointPt ?? regionPt ?? ctrl?.getRegionCanvasPickPoint?.(id, r) ?? null;
    },
    { id: figureId, region, joint },
  );
  expect(point, `${region} has a canvas point`).toBeTruthy();
  const box = await page.locator("canvas[data-testid='posecraft-babylon-canvas']").boundingBox();
  expect(box).toBeTruthy();
  await page.mouse.click(box!.x + point.x, box!.y + point.y);
  await page.waitForTimeout(280);
}

async function applyPoseCard(page: Page, poseId: string) {
  const toggle = page.getByTestId("posecraft-accordion-toggle-pose-library");
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  const card = page.getByTestId(`posecraft-pose-${poseId}`);
  await expect(card).toBeEnabled({ timeout: 10_000 });
  await card.click({ force: true });
}

async function setJointSlider(page: Page, axis: "x" | "y" | "z", value: number) {
  await page.getByTestId(`posecraft-joint-${axis}`).evaluate((el, val) => {
    const input = el as HTMLInputElement;
    const proto = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
    proto?.set?.call(input, String(val));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

test.describe("PoseCraft Visual Truth Law", () => {
  test("Adult Female 7-region picking selects the matching joint", async ({ page, request }) => {
    await openPoseCraft(page);
    const female = await ensureArchetype(page, request, "adult-female");
    await waitReady(page, female.id);
    await selectFigure(page, female.id);
    await page.getByTestId("posecraft-reset-pose").click();
    await page.waitForTimeout(400);
    await frameFigure(page, female.id);

    const box = await page.locator("canvas[data-testid='posecraft-babylon-canvas']").boundingBox();
    expect(box).toBeTruthy();

    for (const [region, joint] of SEVEN_REGIONS) {
      const handle = await page.evaluate(
        ({ id, j }) => {
          const ctrl = (window as any).__posecraftController;
          ctrl?.scene?.render?.();
          return ctrl?.getJointCanvasPoint?.(id, j);
        },
        { id: female.id, j: joint },
      );
      expect(handle, `${joint} handle is on screen`).toBeTruthy();
      await page.mouse.click(box!.x + handle.x, box!.y + handle.y);
      await page.waitForTimeout(250);
      const selected = await page.evaluate(() => (window as any).__posecraftController?.getSelectedJoint?.());
      expect(selected, `click ${region} handle`).toBe(joint);
      await expect(page.getByTestId("posecraft-joint-select")).toHaveValue(joint);
    }

    await clickRegion(page, female.id, "leftLowerArm");
    await expect(page.getByTestId("posecraft-joint-select")).toHaveValue("leftElbow");
    await clickRegion(page, female.id, "head");
    await expect(page.getByTestId("posecraft-joint-select")).toHaveValue("head");
  });

  test("Adult Female martial-arts preset changes state AND geometry, then reconstructs", async ({ page, request }) => {
    await openPoseCraft(page);
    const female = await ensureArchetype(page, request, "adult-female");
    await waitReady(page, female.id);
    await selectFigure(page, female.id);
    await page.getByTestId("posecraft-reset-pose").click();
    await page.waitForTimeout(500);

    const regions = ["rightUpperArm", "rightLowerArm", "rightHand", "chest", "head"];
    const before = await captureEvidence(page, female.id, regions);
    expect(before.centers.rightLowerArm).toBeTruthy();

    await applyPoseCard(page, "action-strike");
    await page.waitForFunction(
      (id) => {
        const euler = (window as any).__posecraftController?.getJointEuler?.(id, "rightElbow");
        return euler && Math.abs(euler.x) > 20;
      },
      female.id,
      { timeout: 12_000 },
    );

    const after = await captureEvidence(page, female.id, regions);
    expect(after.joints.rightElbow?.x).not.toBeCloseTo(before.joints.rightElbow?.x ?? 0, 0);
    expect(dist(before.centers.rightLowerArm!, after.centers.rightLowerArm!)).toBeGreaterThan(0.04);
    expect(dist(before.centers.rightHand!, after.centers.rightHand!)).toBeGreaterThan(0.04);
    expect(byteDiff(before.pixels, after.pixels)).toBeGreaterThan(800);

    let persisted = false;
    for (let i = 0; i < 20; i += 1) {
      const scene = await (await request.get(`${API}/api/posecraft/projects/${PROJECT_ID}/scene`)).json();
      const fig = scene.currentScene.figures.find((entry: { id: string }) => entry.id === female.id);
      if (fig?.pose?.rightElbow && Math.abs(fig.pose.rightElbow.x) > 20) {
        persisted = true;
        break;
      }
      await page.waitForTimeout(350);
    }
    expect(persisted, "Strike pose persisted to the project scene").toBeTruthy();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
    await waitReady(page, female.id);
    const reloaded = await captureEvidence(page, female.id, regions);
    expect(reloaded.joints.rightElbow?.x).toBeCloseTo(after.joints.rightElbow?.x ?? 0, 0);
    expect(dist(reloaded.centers.rightLowerArm!, after.centers.rightLowerArm!)).toBeLessThan(0.08);
    expect(dist(reloaded.centers.rightHand!, after.centers.rightHand!)).toBeLessThan(0.08);
  });

  test("manual left elbow rotates forearm+hand and leaves the upper arm still", async ({ page, request }) => {
    await openPoseCraft(page);
    const female = await ensureArchetype(page, request, "adult-female");
    await waitReady(page, female.id);
    await selectFigure(page, female.id);
    await page.getByTestId("posecraft-reset-pose").click();
    await page.waitForTimeout(400);
    await frameFigure(page, female.id);

    await clickRegion(page, female.id, "leftLowerArm");
    await expect(page.getByTestId("posecraft-joint-select")).toHaveValue("leftElbow");
    const elbowAnchor = await page.evaluate(
      (id) => (window as any).__posecraftController?.getJointCanvasPoint?.(id, "leftElbow"),
      female.id,
    );
    const forearmPoint = await page.evaluate(
      (id) => (window as any).__posecraftController?.getRegionCanvasPoint?.(id, "leftLowerArm"),
      female.id,
    );
    expect(elbowAnchor && forearmPoint).toBeTruthy();
    expect(Math.hypot(elbowAnchor.x - forearmPoint.x, elbowAnchor.y - forearmPoint.y)).toBeLessThan(80);

    const before = await captureEvidence(page, female.id, ["leftUpperArm", "leftLowerArm", "leftHand"]);
    await setJointSlider(page, "x", 80);
    await page.waitForFunction(
      (id) => {
        const euler = (window as any).__posecraftController?.getJointEuler?.(id, "leftElbow");
        return euler && Math.round(euler.x) === 80;
      },
      female.id,
      { timeout: 8_000 },
    );
    const after = await captureEvidence(page, female.id, ["leftUpperArm", "leftLowerArm", "leftHand"]);

    expect(after.joints.leftElbow?.x).toBeCloseTo(80, 0);
    expect(dist(before.centers.leftLowerArm!, after.centers.leftLowerArm!)).toBeGreaterThan(0.05);
    expect(dist(before.centers.leftHand!, after.centers.leftHand!)).toBeGreaterThan(0.05);
    expect(dist(before.centers.leftUpperArm!, after.centers.leftUpperArm!)).toBeLessThan(0.04);
    expect(byteDiff(before.pixels, after.pixels)).toBeGreaterThan(400);
  });

  test("all four archetypes load v4 READY and a preset moves visible geometry", async ({ page, request }) => {
    await openPoseCraft(page);
    const archetypes = ["adult-male", "adult-female", "child-boy", "child-girl"] as const;
    const added: string[] = [];
    const knownIds = new Set(
      await page.evaluate(() => (window as any).__posecraftController?.getFigureIds?.() ?? []),
    );
    for (const archetypeId of archetypes) {
      const figure = await ensureArchetype(page, request, archetypeId);
      if (!knownIds.has(figure.id) && archetypeId !== "adult-female" && archetypeId !== "adult-male") {
        added.push(figure.id);
      }
      knownIds.add(figure.id);
      await waitReady(page, figure.id);
      const meta = await page.evaluate((id) => (window as any).__posecraftController?.getFigureMetadata?.(id), figure.id);
      expect(meta.modelId).toBe(`${archetypeId}-lowpoly-v4`);
      expect(meta.visualState).toBe("READY");
      expect(meta.legacyBlockModel).toBe(false);

      await selectFigure(page, figure.id);
      await page.getByTestId("posecraft-reset-pose").click();
      await page.waitForTimeout(400);
      const before = await captureEvidence(page, figure.id, ["rightLowerArm", "rightHand"]);
      await applyPoseCard(page, "action-strike");
      await page.waitForFunction(
        ({ id, beforeY }) => {
          const center = (window as any).__posecraftController?.getRegionWorldCenter?.(id, "rightHand");
          if (!center || !beforeY) return false;
          return Math.hypot(center.x - beforeY.x, center.y - beforeY.y, center.z - beforeY.z) > 0.03;
        },
        { id: figure.id, beforeY: before.centers.rightHand },
        { timeout: 12_000 },
      );
      const after = await captureEvidence(page, figure.id, ["rightLowerArm", "rightHand"]);
      expect(dist(before.centers.rightLowerArm!, after.centers.rightLowerArm!) + dist(before.centers.rightHand!, after.centers.rightHand!)).toBeGreaterThan(0.03);
    }
    for (const id of added) {
      const menu = page.getByTestId(`posecraft-figure-menu-${id}`);
      if (await menu.count()) {
        await menu.click();
        await page.getByRole("button", { name: "Delete" }).click();
        await page.waitForTimeout(200);
      }
    }
  });

  test("Camera mode never activates figure gizmos", async ({ page }) => {
    await openPoseCraft(page);
    await page.getByTestId("posecraft-gizmo-camera").click();
    const mode = await page.evaluate(() => (window as any).__posecraftController?.getGizmoMode?.());
    expect(mode).toBe("camera");
  });

  test("Co-Director apply_pose writes joints and the viewport geometry changes", async ({ page, request }) => {
    await openPoseCraft(page);
    const female = await ensureArchetype(page, request, "adult-female");
    await waitReady(page, female.id);
    await selectFigure(page, female.id);
    await page.getByTestId("posecraft-reset-pose").click();
    await page.waitForTimeout(500);
    const before = await captureEvidence(page, female.id, ["rightLowerArm", "rightHand", "chest"]);

    let proposalId = "";
    let lastError = "";
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const proposal = await request.post(`${API}/api/codirector/projects/${PROJECT_ID}/tools/proposals`, {
          data: { toolId: "posecraft.apply_pose", arguments: { figureId: female.id, posePresetId: "action-strike" } },
          timeout: 45_000,
        });
        if (proposal.ok()) {
          proposalId = (await proposal.json()).id;
          break;
        }
        lastError = `${proposal.status()}`;
      } catch (error) {
        lastError = String(error);
      }
      await page.waitForTimeout(800);
    }
    expect(proposalId, `apply_pose proposal failed: ${lastError}`).toBeTruthy();
    const approved = await request.post(`${API}/api/codirector/projects/${PROJECT_ID}/proposals/${proposalId}/approve`, {
      data: {},
    });
    expect(approved.ok(), approved.status().toString()).toBeTruthy();
    const receipt = await (await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/proposals/${proposalId}/receipt`)).json();
    expect(receipt.toolResult.applied).toBe(true);
    expect(receipt.toolResult.posePresetId).toBe("action-strike");

    const scene = await (await request.get(`${API}/api/posecraft/projects/${PROJECT_ID}/scene`)).json();
    const fig = scene.currentScene.figures.find((entry: { id: string }) => entry.id === female.id);
    expect(fig.pose.rightElbow.x).toBeGreaterThan(20);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("posecraft-workspace")).toBeVisible({ timeout: 60_000 });
    await waitReady(page, female.id);
    const after = await captureEvidence(page, female.id, ["rightLowerArm", "rightHand", "chest"]);
    expect(after.joints.rightElbow?.x).toBeGreaterThan(20);
    expect(dist(before.centers.rightLowerArm!, after.centers.rightLowerArm!)).toBeGreaterThan(0.04);
    expect(byteDiff(before.pixels, after.pixels)).toBeGreaterThan(800);
  });
});
