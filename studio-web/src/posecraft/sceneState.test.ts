import { describe, expect, it } from "vitest";
import { POSE_LIBRARY } from "./constants";
import { commitHistory, createHistoryState, redoHistory, undoHistory } from "./history";
import {
  addFigure,
  applyPosePreset,
  clampRotation,
  createDefaultDocument,
  createDefaultScene,
  migrateSceneToCurrent,
  restoreSceneVersion,
  saveSceneVersion,
  updateFigureJoint,
} from "./state";
import { parsePoseCraftDocument } from "./storage";
import { POSECRAFT_SCHEMA_VERSION } from "./types";

describe("PoseCraft scene state", () => {
  it("clamps joint rotations to safe limits", () => {
    expect(clampRotation("leftElbow", "x", 999)).toBe(145);
    expect(clampRotation("head", "y", -999)).toBe(-60);
  });

  it("applies pose presets without dropping other joints", () => {
    const scene = createDefaultScene();
    const figureId = scene.figures[0]!.id;
    const next = applyPosePreset(scene, figureId, POSE_LIBRARY[0]!);
    expect(next.figures[0]!.pose.chest.x).toBe(6);
    expect(next.figures[0]!.pose.leftKnee.x).toBe(0);
    expect(next.revision).toBe(scene.revision + 1);
  });

  it("records undo and redo history", () => {
    const first = createDefaultScene();
    const second = addFigure(first, "child-girl");
    const third = updateFigureJoint(second, second.figures[0]!.id, "head", "y", 18);
    const history = commitHistory(commitHistory(createHistoryState(first), second), third);
    const undone = undoHistory(history);
    const redone = redoHistory(undone);
    expect(undone.present.figures.length).toBe(second.figures.length);
    expect(redone.present.figures[0]!.pose.head.y).toBe(18);
  });

  it("saves and restores local versions", () => {
    const baseDocument = createDefaultDocument();
    const saved = saveSceneVersion(baseDocument, "Master");
    expect(saved.savedVersions).toHaveLength(1);
    const restored = restoreSceneVersion(saved, saved.savedVersions[0]!.id);
    expect(restored.currentScene.name).toBe(baseDocument.currentScene.name);
    expect(restored.currentScene.revision).toBeGreaterThan(baseDocument.currentScene.revision);
  });

  it("falls back gracefully from malformed local storage", () => {
    const parsed = parsePoseCraftDocument("{not-valid");
    expect(parsed.currentScene.figures.length).toBeGreaterThan(0);
    expect(parsed.schemaVersion).toBe(POSECRAFT_SCHEMA_VERSION);
  });

  it("Master Program Phase 4.5 — migrates legacy block-figure scenes preserving protected fields", () => {
    // A GREEN-baseline saved scene (schemaVersion 1) with an unsupported
    // legacy joint ("tailBone") and a missing known joint ("leftKnee").
    const legacyScene = {
      schemaVersion: 1,
      revision: 7,
      updatedAt: "2026-08-01T00:00:00Z",
      name: "Legacy Coffee Block",
      notes: "pre-upgrade scene",
      stage: { gridSize: 12, showAxes: true, showPrimitives: true },
      camera: {
        lensMm: 40, aspect: "16:9", guides: ["safe", "thirds"],
        alpha: -1.57, beta: 1.12, radius: 7.5, target: { x: 0, y: 1.2, z: 0 },
      },
      figures: [
        {
          id: "fig-legacy-1", name: "Eli", archetypeId: "adult-male",
          colorId: "teal", position: { x: -0.8, z: 0 }, rotationY: 12, scale: 1.0,
          pose: { head: { x: 0, y: 10, z: 0 }, tailBone: { x: 5, y: 0, z: 0 } },
          characterId: "char-eli",
        },
      ],
      primitives: [],
      selectedFigureId: "fig-legacy-1",
      selectedJoint: "head",
    } as unknown as import("./types").PoseCraftScene;

    const migrated = migrateSceneToCurrent(legacyScene);
    // schema bumped to current
    expect(migrated.schemaVersion).toBe(POSECRAFT_SCHEMA_VERSION);
    // protected fields preserved
    expect(migrated.revision).toBe(7);
    expect(migrated.name).toBe("Legacy Coffee Block");
    expect(migrated.camera.lensMm).toBe(40);
    const fig = migrated.figures[0]!;
    expect(fig.id).toBe("fig-legacy-1");
    expect(fig.name).toBe("Eli");
    expect(fig.archetypeId).toBe("adult-male");
    // legacy color "teal" remapped to current "seaglass" (same hex #0f766e)
    expect(fig.colorId).toBe("seaglass");
    expect(fig.position).toEqual({ x: -0.8, z: 0 });
    expect(fig.rotationY).toBe(12);
    expect(fig.scale).toBe(1.0);
    expect(fig.characterId).toBe("char-eli");
    // known joint preserved
    expect(fig.pose.head).toEqual({ x: 0, y: 10, z: 0 });
    // missing known joint filled with neutral
    expect(fig.pose.leftKnee).toEqual({ x: 0, y: 0, z: 0 });
    // unsupported legacy joint retained in provenance, not in pose
    expect(fig.legacyJointData?.tailBone).toEqual({ x: 5, y: 0, z: 0 });
    expect(fig.pose).not.toHaveProperty("tailBone");
    // migration provenance recorded
    expect(migrated.provenance?.migratedFrom).toBe(1);
    expect(migrated.provenance?.migratedAt).toBeTruthy();

    // Idempotent: re-running migration does not re-record a migration and
    // keeps protected fields + legacy data intact.
    const rerun = migrateSceneToCurrent(migrated);
    expect(rerun.schemaVersion).toBe(POSECRAFT_SCHEMA_VERSION);
    expect(rerun.figures[0]!.id).toBe("fig-legacy-1");
    expect(rerun.figures[0]!.pose.head.y).toBe(10);
    expect(rerun.figures[0]!.legacyJointData?.tailBone?.x).toBe(5);
    expect(rerun.provenance?.migratedFrom).toBe(1);
  });
});
