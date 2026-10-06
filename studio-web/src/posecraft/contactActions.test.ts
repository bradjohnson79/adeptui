import { describe, expect, it } from "vitest";
import { focusCamera, lookFigureAt, sitFigureOnObject } from "./contactActions";
import { createDefaultScene, createFigure, migrateSceneToCurrent } from "./state";
import { humanoidBoneHints, pluginExtensionForAsset } from "./meshLoader";
import { creatorGroupForPose } from "./posePresentation";

describe("PoseCraft previz rebuild client contracts", () => {
  it("migrates schema 2 primitives into objects without dropping ids", () => {
    const scene = migrateSceneToCurrent({
      ...createDefaultScene(),
      schemaVersion: 2,
      objects: [],
      environment: undefined as never,
      primitives: [
        {
          id: "prim-table",
          name: "Mess table",
          kind: "table-medium",
          position: { x: 0.4, z: 1.1 },
          rotationY: 12,
          scale: 1,
          size: { x: 1.6, y: 0.75, z: 0.8 },
          color: "#94a3b8",
        },
      ],
    });
    expect(scene.schemaVersion).toBe(3);
    expect(scene.objects[0].id).toBe("prim-table");
    expect(scene.objects[0].source).toBe("procedural");
    expect(scene.environment.source).toBe("none");
  });

  it("sits a figure on an object and looks at a partner", () => {
    const lead = createFigure("adult-female");
    const partner = createFigure("adult-male");
    lead.id = "fig-korri";
    partner.id = "fig-ana";
    partner.position = { x: 2, z: 0 };
    let scene = migrateSceneToCurrent({
      ...createDefaultScene(),
      figures: [lead, partner],
      objects: [
        {
          id: "obj-chair",
          name: "chair",
          source: "procedural",
          position: { x: 1.2, y: 0, z: -0.3 },
          size: { x: 0.5, y: 0.8, z: 0.5 },
        },
      ],
    });
    scene = sitFigureOnObject(scene, "fig-korri", "obj-chair");
    expect(scene.figures[0].position.x).toBeCloseTo(1.2);
    expect(scene.figures[0].poseId).toBe("rest-seated");
    scene = lookFigureAt(scene, "fig-korri", "fig-ana");
    expect(scene.figures[0].eyelineTargetId).toBe("fig-ana");
  });

  it("allows face-level camera radius below the old 2.2 floor", () => {
    const figure = createFigure("adult-female");
    figure.id = "fig-korri";
    const scene = focusCamera(
      migrateSceneToCurrent({ ...createDefaultScene(), figures: [figure] }),
      "face",
      "fig-korri",
    );
    expect(scene.camera.minZ).toBe(0.05);
    expect(scene.camera.radius).toBeLessThan(1);
    expect(scene.camera.focusKind).toBe("face");
  });

  it("resolves /file loader extension from the stored filename", () => {
    expect(pluginExtensionForAsset("mess-hall-table.glb")).toBe(".glb");
    expect(pluginExtensionForAsset("prop.obj")).toBe(".obj");
    expect(pluginExtensionForAsset("asset-without-dot", "mesh-3d")).toBe(".glb");
  });

  it("does not treat an unrigged mesh name as a poseable joint", () => {
    expect(humanoidBoneHints("Cube.001")).toBeNull();
    expect(humanoidBoneHints("mixamorig:Head")).toBe("head");
  });

  it("presents walking poses as creator walk frames", () => {
    expect(creatorGroupForPose("motion-walk", "motion")).toBe("Walking");
    expect(creatorGroupForPose("rest-seated", "rest")).toBe("Sitting");
    expect(creatorGroupForPose("rest-reclined", "rest")).toBe("Lying Down");
  });
});
