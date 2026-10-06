import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("LibraryMediaGrid Add Media", () => {
  it("wires a creator Add Media upload control", () => {
    const src = readFileSync(new URL("./LibraryMediaGrid.tsx", import.meta.url), "utf8");
    expect(src).toContain('data-testid="library-add-media"');
    expect(src).toContain('data-testid="library-add-media-input"');
    expect(src).toContain("api.uploadAsset");
    expect(src).toContain("inferLibraryUploadKind");
  });
});
