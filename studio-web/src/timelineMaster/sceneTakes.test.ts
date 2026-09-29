import { describe, expect, it } from "vitest";
import { sceneTakeDisplayLabel, sceneTakeIsListed, sceneTakeLetter } from "./sceneTakes";

describe("sceneTakeLetter", () => {
  it("maps 1–26 to A–Z and 27+ to Z1…", () => {
    expect(sceneTakeLetter(1)).toBe("A");
    expect(sceneTakeLetter(2)).toBe("B");
    expect(sceneTakeLetter(26)).toBe("Z");
    expect(sceneTakeLetter(27)).toBe("Z1");
    expect(sceneTakeLetter(28)).toBe("Z2");
  });
});

describe("sceneTakeIsListed", () => {
  it("stays hidden until a generation has completed or is rendering", () => {
    expect(sceneTakeIsListed({ status: "incomplete", batches: [] })).toBe(false);
    expect(sceneTakeIsListed({ status: "cancelled", batches: [{ assetId: "" }] })).toBe(false);
    expect(sceneTakeIsListed({ status: "rendering", batches: [] })).toBe(true);
    expect(sceneTakeIsListed({ status: "incomplete", resultAssetId: "asset-1", batches: [] })).toBe(true);
    expect(sceneTakeIsListed({ status: "ready", batches: [{ assetId: "asset-1" }] })).toBe(true);
  });
});

describe("sceneTakeDisplayLabel", () => {
  it("prefixes Take once", () => {
    expect(sceneTakeDisplayLabel("B")).toBe("Take B");
    expect(sceneTakeDisplayLabel("Take C")).toBe("Take C");
  });
});
