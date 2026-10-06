import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");
const grid = readFileSync(new URL("./SpatialGrid.tsx", import.meta.url), "utf8");
const inspector = readFileSync(new URL("./CameraInspector.tsx", import.meta.url), "utf8");
const types = readFileSync(new URL("./types.ts", import.meta.url), "utf8");

describe("Spatial Map restore wiring locks", () => {
  it("passes full-sequence movement arrows into SpatialGrid overlay", () => {
    expect(panel).toContain("movementArrows={movementArrows}");
    expect(panel).toContain("fullSequence: true");
    expect(grid).toContain('data-testid="spatial-map-movement-arrows"');
    expect(grid).toContain("markerEnd=\"url(#spatial-map-movement-arrowhead)\"");
  });

  it("builds Primary Subject from enabled Characters panel entities in inspector + card", () => {
    expect(panel).toContain("primarySubjectOptions(document?.characters || [])");
    expect(panel).toContain("subjectOptions={cameraSubjectOptions}");
    expect(panel).toContain("camerasNeedingSubjectFallback");
    expect(inspector).toContain("subjectOptions.map");
    expect(inspector).not.toMatch(/Korri|Anadriya/);
  });
});

describe("Spatial Map camera movement path wiring locks", () => {
  it("derives green path from camera segment poses, not character follow", () => {
    expect(panel).toContain("cameraMovementArrows={cameraMovementArrows}");
    expect(panel).toContain("document?.movementSegments");
    expect(panel).toContain("computeCameraMovementArrows(");
    expect(grid).toContain('data-testid="spatial-map-camera-movement-arrows"');
    expect(grid).toContain("markerEnd=\"url(#spatial-map-camera-movement-arrowhead)\"");
    expect(grid).toContain("rgba(74, 222, 128");
  });
});

describe("Spatial Map free-camera + POV wiring locks", () => {
  it("POV is a Shot Size option and is the only attach mode", () => {
    expect(types).toContain('"pov"');
    expect(inspector).toContain("SHOT_SIZES.map");
    expect(inspector).toContain("camera-shot-size");
    expect(panel).toContain('next === "pov" ? "pov" : "free"');
    expect(grid).toContain("resolvePovCameraScrubPosition");
    expect(grid).toContain("resolveCameraAttachMode");
    expect(grid).toContain("data-attach-mode");
    expect(grid).not.toContain("resolveFollowCameraScrubPosition");
    expect(grid).not.toContain("resolveCameraScrubPosition");
  });
});
