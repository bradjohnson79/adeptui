import { describe, expect, it } from "vitest";
import { characterMediaUrl, isCanonicalAssetFileUrl } from "./characterMediaUrl";

describe("characterMediaUrl", () => {
  it("accepts the canonical project-scoped asset file route", () => {
    expect(characterMediaUrl("/api/projects/p1/assets/abc-123/file")).toBe(
      "/api/projects/p1/assets/abc-123/file",
    );
    expect(isCanonicalAssetFileUrl("/api/projects/p1/assets/abc-123/file")).toBe(true);
  });

  it("refuses the retired unscoped path", () => {
    expect(characterMediaUrl("/api/assets/abc-123/file")).toBe("");
    expect(isCanonicalAssetFileUrl("/api/assets/abc-123/file")).toBe(false);
  });

  it("refuses filesystem paths and /api/file fallbacks", () => {
    expect(characterMediaUrl("C:\\\\data\\\\assets\\\\abc.png")).toBe("");
    expect(characterMediaUrl("/api/file?path=projects/p1/assets/abc.png")).toBe("");
    expect(characterMediaUrl("")).toBe("");
  });
});
