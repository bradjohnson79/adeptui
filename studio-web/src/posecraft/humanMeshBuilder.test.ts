import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  BODY_REGIONS,
  HUMAN_MODEL_IDS,
  buildHumanMeshMetadata,
  figureExportMetadata,
  figureIdentity,
} from "./humanMeshBuilder";

describe("PoseCraft v3 human figures", () => {
  it("uses v3 model ids and a 17-joint rig", () => {
    expect(HUMAN_MODEL_IDS["adult-male"]).toBe("adult-male-lowpoly-v3");
    expect(HUMAN_MODEL_IDS["adult-female"]).toBe("adult-female-lowpoly-v3");
    expect(HUMAN_MODEL_IDS["child-boy"]).toBe("child-boy-lowpoly-v3");
    expect(HUMAN_MODEL_IDS["child-girl"]).toBe("child-girl-lowpoly-v3");
    const meta = buildHumanMeshMetadata("adult-male", 2480, 1.84);
    expect(meta.jointCount).toBe(17);
    expect(meta.bodyRegions).toHaveLength(BODY_REGIONS.length);
    expect(meta.legacyBlockModel).toBe(false);
    expect(meta.rig).toBe("posecraft-v2");
  });

  it("keeps boy and girl distinct and ships GLB metadata", () => {
    expect(figureIdentity("child-boy")).toEqual({ gender: "male", ageClass: "child" });
    expect(figureIdentity("child-girl")).toEqual({ gender: "female", ageClass: "child" });
    const json = JSON.parse(
      readFileSync(new URL("../../public/posecraft/figures/adult-female-lowpoly-v3.json", import.meta.url), "utf8"),
    );
    expect(json.modelId).toBe("adult-female-lowpoly-v3");
    expect(json.jointCount).toBe(17);
    expect(json.pose).toBe("T-pose");
    expect(json.triangleCount).toBeGreaterThanOrEqual(2000);
    expect(json.triangleCount).toBeLessThanOrEqual(5000);
    const exported = figureExportMetadata("adult-female", 1.7, json.triangleCount);
    expect(exported.triangleCount).toBe(json.triangleCount);
    const glb = readFileSync(new URL("../../public/posecraft/figures/adult-female-lowpoly-v3.glb", import.meta.url));
    expect(glb.subarray(0, 4).toString()).toBe("glTF");
    expect(glb.length).toBeGreaterThan(1000);
  });
});
