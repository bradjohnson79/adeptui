import { describe, expect, it } from "vitest";
import { libraryThumbKind, libraryThumbUrl } from "./libraryThumb";

describe("libraryThumbUrl", () => {
  it("uses /thumb for images and videos", () => {
    expect(libraryThumbUrl("proj", "asset-1", "image")).toContain("/api/projects/proj/assets/asset-1/thumb");
    expect(libraryThumbUrl("proj", "asset-2", "video")).toContain("/thumb?w=256");
  });

  it("never requests /thumb for audio", () => {
    expect(libraryThumbUrl("proj", "asset-3", "audio")).toBeNull();
    expect(libraryThumbUrl("proj", "asset-4", "music")).toBeNull();
    expect(libraryThumbKind("sfx")).toBe("audio");
  });
});
