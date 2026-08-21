import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { BODY_REGIONS, REGION_TO_JOINT } from "./humanMeshBuilder";
import { missingV4Regions, V4_REQUIRED_REGIONS } from "./v4FigureLoader";
import { isLoadCurrent } from "./v4RestJoints";

describe("v4 interaction contracts", () => {
  it("keeps the 17-region name map", () => {
    expect(V4_REQUIRED_REGIONS).toEqual(BODY_REGIONS);
    expect(REGION_TO_JOINT.leftLowerArm).toBe("leftElbow");
    expect(REGION_TO_JOINT.leftUpperArm).toBe("leftShoulder");
    expect(Object.keys(REGION_TO_JOINT)).toHaveLength(17);
  });

  it("rejects a GLB that is missing required regions", () => {
    expect(missingV4Regions(new Map())).toEqual([...BODY_REGIONS]);
  });

  it("does not instantiate the procedural builder for default archetypes", () => {
    const engine = readFileSync(new URL("./engine.ts", import.meta.url), "utf8");
    expect(engine).not.toMatch(/buildHumanBody\s*\(/);
    expect(engine).toMatch(/attachV4Figure/);
  });

  it("carries selectedJoint on select and does not map Camera to Move", () => {
    const workspace = readFileSync(new URL("../components/GenerationTools/PoseCraftWorkspace.tsx", import.meta.url), "utf8");
    expect(workspace).toMatch(/selectedJoint: event\.joint \?\? current\.selectedJoint/);
    expect(workspace).toMatch(/setGizmoMode\("camera"\)/);
    expect(workspace).not.toMatch(/data-testid="posecraft-gizmo-camera"[\s\S]{0,180}setGizmoMode\("move"\)/);
  });

  it("sanitizes sync during drag and gates controls until READY", () => {
    const engine = readFileSync(new URL("./engine.ts", import.meta.url), "utf8");
    expect(engine).toMatch(/if \(!this\.drag\) \{\s*this\.selectedJoint = sceneDoc\.selectedJoint/s);
    // Per-figure gate: only the actively dragged figure skips state writes.
    expect(engine).not.toMatch(/figure\.pose\[this\.selectedJoint\] !== undefined[\s\S]{0,40}: "spine"/);
    expect(engine).toMatch(/const dragging = this\.drag\?\.figureId === figure\.id/);
    expect(engine).toMatch(/if \(!dragging\) \{/);
    expect(engine).toMatch(/visualState !== "READY"/);
    expect(engine).toMatch(/gizmoMode === "camera"/);
  });

  it("discards a completed load after dispose", () => {
    expect(isLoadCurrent(1, 1, "DISPOSED")).toBe(false);
    expect(isLoadCurrent(1, 1, "LOADING")).toBe(true);
  });

  it("clears rotationQuaternion and applies bind rotation on clone attach", () => {
    const loader = readFileSync(new URL("./v4FigureLoader.ts", import.meta.url), "utf8");
    expect(loader).toMatch(/mesh\.rotationQuaternion = null/);
    expect(loader).toMatch(/mesh\.rotation\.set\(0, 0, V4_REGION_BIND_ROTATION_Z\[region\]\)/);
    expect(loader).toMatch(/backFaceCulling = false/);
    expect(loader).toMatch(/kind: "body"/);
    expect(loader).toMatch(/attachPickCollider/);
  });

  it("attaches invisible pick colliders with figureId/region/kind metadata", () => {
    const loader = readFileSync(new URL("./v4FigureLoader.ts", import.meta.url), "utf8");
    expect(loader).toMatch(/export function attachPickCollider/);
    expect(loader).toMatch(/collider\.isVisible = false/);
    expect(loader).toMatch(/collider\.isPickable = true/);
    expect(loader).toMatch(/kind: "collider"/);
    expect(loader).toMatch(/collider\.parent = mesh/);
  });

  it("picks in CSS space and prefers exact body hits over colliders", () => {
    const engine = readFileSync(new URL("./engine.ts", import.meta.url), "utf8");
    expect(engine).toMatch(/evt\.clientX - rect\.left/);
    expect(engine).toMatch(/evt\.clientY - rect\.top/);
    expect(engine).not.toMatch(/hardwareScalingLevel/);
    expect(engine).toMatch(/kindPick\("body"\)/);
    expect(engine).toMatch(/kindPick\("collider"\)/);
    expect(engine).toMatch(/mesh\.isEnabled\(true\)/);
  });

  it("clears drag on cancel, leave, mode switch, and selection change", () => {
    const engine = readFileSync(new URL("./engine.ts", import.meta.url), "utf8");
    expect(engine).toMatch(/addEventListener\("pointercancel"/);
    expect(engine).toMatch(/addEventListener\("pointerleave"/);
    expect(engine).toMatch(/if \(this\.drag\) this\.cancelDrag\(\)/);
    expect(engine).toMatch(/private cancelDrag\(\)/);
    expect(engine).toMatch(/private endDrag\(/);
    expect(engine).toMatch(/onPointerObservable\.add\([\s\S]*?,\s*-1,\s*true\)/);
  });

  it("exposes Visual Truth Law geometry probes", () => {
    const engine = readFileSync(new URL("./engine.ts", import.meta.url), "utf8");
    expect(engine).toMatch(/getRegionWorldCenter\(/);
    expect(engine).toMatch(/getRegionCanvasPickPoint\(/);
    expect(engine).toMatch(/getJointWorldPosition\(/);
    expect(engine).toMatch(/getJointCanvasPoint\(/);
    expect(engine).toMatch(/getJointEuler\(/);
  });
});
