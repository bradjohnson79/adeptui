import { describe, expect, it } from "vitest";
import { applyPosePreset, createDefaultScene, updateFigure } from "./state";
import { POSE_CATALOG, getPoseById } from "./poseCatalog";
import { loadPoseCraftDocument, savePoseCraftDocument } from "./storage";
import type { JointName, PoseCraftDocument } from "./types";

function memoryStore(): { getItem: (k: string) => string | null; setItem: (k: string, v: string) => void } {
  const map = new Map<string, string>();
  return {
    getItem: (k) => (map.has(k) ? map.get(k)! : null),
    setItem: (k, v) => { map.set(k, v); },
  };
}

function roundTrip(doc: PoseCraftDocument): PoseCraftDocument {
  const store = memoryStore();
  savePoseCraftDocument(store, doc);
  return loadPoseCraftDocument(store);
}

/**
 * Master Program Phase 12–14: manipulation evidence.
 * Proves the round-trip: viewport manipulation → canonical state →
 * save (API/local persistence) → reload → match. The engine emits
 * ManipulationEvent values; this test exercises the canonical-state
 * mutators that the React handler calls, then saves and reloads.
 */
describe("PoseCraft manipulation round-trip (viewport → canonical → save → reload → match)", () => {
  it("move: figure position survives save + reload", () => {
    let scene = createDefaultScene();
    const figureId = scene.figures[0]!.id;
    scene = updateFigure(scene, figureId, { position: { x: 1.5, y: 0, z: -0.8 } });
    const reloaded = roundTrip({ currentScene: scene, savedVersions: [] });
    const reloadedFig = reloaded.currentScene.figures.find((f) => f.id === figureId)!;
    expect(reloadedFig.position.x).toBe(1.5);
    expect(reloadedFig.position.z).toBe(-0.8);
  });

  it("rotate: figure rotationY survives save + reload", () => {
    let scene = createDefaultScene();
    const figureId = scene.figures[0]!.id;
    scene = updateFigure(scene, figureId, { rotationY: 42 });
    const reloaded = roundTrip({ currentScene: scene, savedVersions: [] });
    const reloadedFig = reloaded.currentScene.figures.find((f) => f.id === figureId)!;
    expect(reloadedFig.rotationY).toBe(42);
  });

  it("pose: a single joint rotation survives save + reload", () => {
    let scene = createDefaultScene();
    const figureId = scene.figures[0]!.id;
    const fig = scene.figures.find((f) => f.id === figureId)!;
    scene = updateFigure(scene, figureId, {
      pose: { ...fig.pose, rightShoulder: { x: 12, y: 0, z: 30 } as never },
    });
    const reloaded = roundTrip({ currentScene: scene, savedVersions: [] });
    const reloadedFig = reloaded.currentScene.figures.find((f) => f.id === figureId)!;
    expect(reloadedFig.pose["rightShoulder"]).toEqual({ x: 12, y: 0, z: 30 });
  });

  it("applyPosePreset (catalog pose) survives save + reload and matches catalog joints", () => {
    let scene = createDefaultScene();
    const figureId = scene.figures[0]!.id;
    const preset = getPoseById("dialogue-listen")!;
    scene = applyPosePreset(scene, figureId, preset);
    const reloaded = roundTrip({ currentScene: scene, savedVersions: [] });
    const reloadedFig = reloaded.currentScene.figures.find((f) => f.id === figureId)!;
    for (const joint of Object.keys(preset.joints) as JointName[]) {
      expect(reloadedFig.pose[joint], `${joint} should match catalog`).toEqual(preset.joints[joint]);
    }
  });

  it("a full manipulation sequence (move + rotate + pose + preset) survives save + reload", () => {
    let scene = createDefaultScene();
    const figureId = scene.figures[0]!.id;
    scene = updateFigure(scene, figureId, { position: { x: 2, y: 0, z: 1 } });
    scene = updateFigure(scene, figureId, { rotationY: -15 });
    const fig = scene.figures.find((f) => f.id === figureId)!;
    scene = updateFigure(scene, figureId, {
      pose: { ...fig.pose, leftElbow: { x: 0, y: 0, z: 45 } as never },
    });
    const preset = getPoseById("power-hips")!;
    scene = applyPosePreset(scene, figureId, preset);
    const reloaded = roundTrip({ currentScene: scene, savedVersions: [] });
    const reloadedFig = reloaded.currentScene.figures.find((f) => f.id === figureId)!;
    expect(reloadedFig.position.x).toBe(2);
    expect(reloadedFig.position.z).toBe(1);
    expect(reloadedFig.rotationY).toBe(-15);
    // preset overrides the earlier leftElbow tweak
    expect(reloadedFig.pose["leftElbow"]).toEqual(preset.joints["leftElbow"]);
  });

  it("the catalog has >= 50 poses available for manipulation", () => {
    expect(POSE_CATALOG.length).toBeGreaterThanOrEqual(50);
  });
});
