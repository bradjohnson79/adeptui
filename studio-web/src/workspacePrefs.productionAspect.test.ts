import { describe, expect, it } from "vitest";
import { PRODUCTION_ASPECTS, normalizeProductionAspect } from "./workspacePrefs";

describe("PRODUCTION_ASPECTS 9:16", () => {
  it("lists 9:16 immediately after 16:9", () => {
    expect([...PRODUCTION_ASPECTS]).toEqual(["1:1", "4:3", "16:9", "9:16", "21:9"]);
  });

  it("normalize accepts 9:16", () => {
    expect(normalizeProductionAspect("9:16")).toBe("9:16");
    expect(normalizeProductionAspect("nope")).toBe("16:9");
  });
});
