import { describe, expect, it } from "vitest";
import {
  buildDisplayInstruction,
  canLockCamera,
  lockIsValid,
  validateCameraCommand,
  type SceneCameraRecord,
} from "./cameraCommandEngine";

function record(partial: Partial<SceneCameraRecord> = {}): SceneCameraRecord {
  const pose = {
    cameraId: "c1",
    cameraSlot: 0,
    label: "Camera 1",
    gridColumn: 4,
    gridRow: 5,
    normalizedX: 0,
    normalizedY: 0,
    yawDegrees: 0,
    pitchDegrees: 0,
    heightMeters: 1.6,
    orientation: "N",
    fovPreset: "medium",
    lensMm: 35,
    opticalZoomStep: 0,
    physicalStepOffset: { forwardBack: 0, leftRight: 0, vertical: 0 },
    anglePreset: "eye_level" as const,
    shotType: "extreme_close_up",
    targetEntityId: "korri",
    targetEntityType: "character" as const,
  };
  return {
    cameraId: "c1",
    cameraSlot: 0,
    label: "Camera 1",
    enabled: true,
    baseline: pose,
    current: pose,
    history: [],
    cameraStateVersion: 7,
    cameraStateHash: "abc123",
    structuredCommand: {},
    displayInstruction: "CAMERA 1 take EXTREME CLOSE-UP on CHARACTER 1.",
    userCameraPromptDelta: "",
    lineage: {
      cameraId: "c1",
      cameraStateVersion: 7,
      cameraStateHash: "abc123",
      previewStatus: "ready",
      previewStateVersion: 7,
      previewStateHash: "abc123",
      previewAssetId: "prev",
      locked: true,
      lockedStateVersion: 7,
      lockedStateHash: "abc123",
    },
    ...partial,
  };
}

describe("cinematographer command engine", () => {
  it("builds the ECU on Character 1 prompt", () => {
    expect(
      buildDisplayInstruction({
        cameraSlot: 0,
        operationId: "extreme_close_up",
        characterId: "korri",
        characterName: "Korri",
        characterSlot: 1,
      }),
    ).toBe("CAMERA 1 take EXTREME CLOSE-UP on CHARACTER 1, Korri.");
  });

  it("builds one step back without a target", () => {
    expect(
      buildDisplayInstruction({
        cameraSlot: 1,
        operationId: "step_back",
      }),
    ).toBe("CAMERA 2 move ONE STEP BACK.");
  });

  it("requires a subject for framing", () => {
    const result = validateCameraCommand("extreme_close_up", "", "");
    expect(result.ok).toBe(false);
  });

  it("allows skip for a physical step", () => {
    const result = validateCameraCommand("step_back", "", "");
    expect(result.ok).toBe(true);
  });

  it("does not unlock when the preview asset is missing", () => {
    const rec = record({
      lineage: {
        cameraId: "c1",
        cameraStateVersion: 7,
        cameraStateHash: "abc123",
        locked: true,
        lockedStateVersion: 7,
        lockedStateHash: "abc123",
        previewStatus: "ready",
        previewStateVersion: 7,
        previewAssetId: "",
      },
    });
    expect(lockIsValid(rec)).toBe(true);
    expect(canLockCamera(rec)).toBe(true);
  });

  it("treats a version bump as stale lock", () => {
    const rec = record({ cameraStateVersion: 8, cameraStateHash: "newhash" });
    expect(lockIsValid(rec)).toBe(false);
  });
});
