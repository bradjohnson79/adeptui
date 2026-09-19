import { describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { voiceTakeAudioSrc } from "./voiceTakeAudioSrc";

describe("voiceTakeAudioSrc", () => {
  it("calls assetUrl with projectId and returns a non-empty project-scoped src", () => {
    const spy = vi.spyOn(api, "assetUrl");
    const projectId = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
    const audioAssetId = "aa000000-0000-4000-8000-000000000001";
    const src = voiceTakeAudioSrc(projectId, audioAssetId);
    expect(spy).toHaveBeenCalledWith(audioAssetId, undefined, projectId);
    expect(src).toBe(`/api/projects/${projectId}/assets/${audioAssetId}/file`);
    expect(src.length).toBeGreaterThan(0);
    spy.mockRestore();
  });

  it("returns empty when audioAssetId is missing so a dead player is not mounted", () => {
    expect(voiceTakeAudioSrc("beffd3d8-791d-4adf-9c4d-681ec9d4efb0", null)).toBe("");
    expect(voiceTakeAudioSrc("beffd3d8-791d-4adf-9c4d-681ec9d4efb0", "")).toBe("");
    expect(voiceTakeAudioSrc("beffd3d8-791d-4adf-9c4d-681ec9d4efb0")).toBe("");
  });
});

describe("api.assetUrl", () => {
  it("keeps a non-empty legacy src when projectId is omitted", () => {
    expect(api.assetUrl("asset-1")).toBe("/api/assets/asset-1/file");
  });

  it("uses the project-scoped file path when projectId is passed", () => {
    expect(api.assetUrl("asset-1", undefined, "proj-9")).toBe(
      "/api/projects/proj-9/assets/asset-1/file",
    );
  });
});
