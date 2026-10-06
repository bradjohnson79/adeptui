import { describe, expect, it } from "vitest";
import {
  canApproveLibraryImage,
  labelForApproveAsKind,
  PREVIEW_APPROVE_AS_OPTIONS,
} from "./previewApproveAs";

describe("previewApproveAs", () => {
  it("offers Character, Environment, Prop, and Scene Frame", () => {
    expect(PREVIEW_APPROVE_AS_OPTIONS.map((item) => item.kind)).toEqual([
      "character",
      "environment",
      "prop",
      "scene_frame",
    ]);
    expect(labelForApproveAsKind("character")).toBe("Character");
    expect(labelForApproveAsKind("scene_frame")).toBe("Scene Frame");
  });

  it("shows the bar only for an open Library image", () => {
    expect(canApproveLibraryImage({ showingLibrary: true, mediaKind: "image", assetKind: "image" })).toBe(true);
    expect(canApproveLibraryImage({ showingLibrary: false, mediaKind: "image", assetKind: "image" })).toBe(false);
    expect(canApproveLibraryImage({ showingLibrary: true, mediaKind: "audio", assetKind: "audio" })).toBe(false);
    expect(canApproveLibraryImage({ showingLibrary: true, mediaKind: "video", assetKind: "video" })).toBe(false);
    expect(canApproveLibraryImage({ showingLibrary: true, filename: "steps.wav" })).toBe(false);
  });
});
