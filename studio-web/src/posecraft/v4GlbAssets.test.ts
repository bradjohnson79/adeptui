import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { BODY_REGIONS } from "./humanMeshBuilder";

const MODELS = [
  "adult-male-lowpoly-v4",
  "adult-female-lowpoly-v4",
  "child-boy-lowpoly-v4",
  "child-girl-lowpoly-v4",
] as const;

function readGlbJson(name: string): Record<string, unknown> {
  const bytes = readFileSync(new URL(`../../public/posecraft/figures/${name}.glb`, import.meta.url));
  expect(bytes.subarray(0, 4).toString()).toBe("glTF");
  const jsonLen = bytes.readUInt32LE(12);
  const json = bytes.subarray(20, 20 + jsonLen).toString("utf8").replace(/\0+$/, "");
  return JSON.parse(json);
}

describe("v4 runtime GLBs", () => {
  it.each(MODELS)("%s has Figure root, 17 regions, and no skins", (modelId) => {
    const gltf = readGlbJson(modelId);
    const nodes = (gltf.nodes as Array<{ name?: string; mesh?: number }>) ?? [];
    const names = nodes.map((node) => node.name);
    expect(names).toContain("Figure");
    for (const region of BODY_REGIONS) {
      expect(names).toContain(region);
    }
    expect(gltf.skins ?? []).toEqual([]);
    expect(gltf.animations ?? []).toEqual([]);
    const bytes = readFileSync(new URL(`../../public/posecraft/figures/${modelId}.glb`, import.meta.url));
    const jsonLen = bytes.readUInt32LE(12);
    const chunk = bytes.subarray(20, 20 + jsonLen);
    expect(() => JSON.parse(chunk.toString("utf8"))).not.toThrow();
  });
});
