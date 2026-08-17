import { describe, expect, it } from "vitest";
import { isReferenceImage, referenceRole } from "./ReferenceBrowser";
import type { LibraryAsset } from "../CoDirector/library/assetModel";

describe("Image Generator reference helpers", () => {
  it("keeps character/prop/location identity when ids exist", () => {
    expect(referenceRole({ id: "1", characterId: "c1", kind: "image" } as LibraryAsset)).toBe("Character");
    expect(referenceRole({ id: "2", propId: "p1", kind: "image" } as LibraryAsset)).toBe("Prop");
    expect(referenceRole({ id: "3", sceneId: "s1", kind: "image" } as LibraryAsset)).toBe("Location");
  });

  it("treats environment assets as reference images", () => {
    expect(isReferenceImage({ id: "e", kind: "environment" })).toBe(true);
    expect(isReferenceImage({ id: "v", kind: "video", mime_type: "video/mp4" })).toBe(false);
  });
});
