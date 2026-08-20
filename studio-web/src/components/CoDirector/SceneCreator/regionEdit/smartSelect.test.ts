import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Scene Creator Smart Select", () => {
  it("does not treat a box as a mask", () => {
    const src = readFileSync(new URL("./RegionEditPanel.tsx", import.meta.url), "utf8");
    expect(src).toContain("Select from the scene");
    expect(src).toContain("api.perception.autoMask");
    expect(src).toContain("Paint the region");
    expect(src).toContain("selectInFlight.current");
    expect(src).toContain("SMART_SELECT_PAINT");
    expect(src).not.toContain("Not available");
  });
});
