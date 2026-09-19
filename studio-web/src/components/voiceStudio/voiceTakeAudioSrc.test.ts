import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { bindAssetProjectId } from "../../runtime/assetProjectBind";
import { voiceTakeAudioSrc } from "./voiceTakeAudioSrc";

afterEach(() => {
  bindAssetProjectId("");
});

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

  it("returns empty when projectId is missing — Ready+duration / 0:00/0:00 pattern", () => {
    expect(voiceTakeAudioSrc("", "aa000000-0000-4000-8000-000000000001")).toBe("");
    expect(api.assetUrl("aa000000-0000-4000-8000-000000000001")).toBe("");
  });

  it("returns empty when audioAssetId is missing so a dead player is not mounted", () => {
    expect(voiceTakeAudioSrc("beffd3d8-791d-4adf-9c4d-681ec9d4efb0", null)).toBe("");
    expect(voiceTakeAudioSrc("beffd3d8-791d-4adf-9c4d-681ec9d4efb0", "")).toBe("");
    expect(voiceTakeAudioSrc("beffd3d8-791d-4adf-9c4d-681ec9d4efb0")).toBe("");
  });
});

describe("api.assetUrl", () => {
  it("builds only project-scoped file URLs when projectId is passed", () => {
    expect(api.assetUrl("asset-1", undefined, "proj-9")).toBe(
      "/api/projects/proj-9/assets/asset-1/file",
    );
  });

  it("returns empty when pid is missing and nothing is bound", () => {
    expect(api.assetUrl("asset-1")).toBe("");
  });

  it("uses the bound project id when callers omit projectId", () => {
    bindAssetProjectId("bound-proj");
    expect(api.assetUrl("asset-1")).toBe("/api/projects/bound-proj/assets/asset-1/file");
  });
});
