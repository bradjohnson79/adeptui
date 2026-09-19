import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { projectIdFromApiPath } from "../../projectSecurity";
import { bindAssetUrlProject } from "../../runtime/assetProjectBind";
import { voiceTakeAudioSrc } from "./voiceTakeAudioSrc";

afterEach(() => {
  bindAssetUrlProject("");
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
    expect(src.includes("/api/assets/")).toBe(false);
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
  it("is the live (assetId, rev?, projectId?) helper, not GitHub beta's one-arg form", () => {
    expect(api.assetUrl.length).toBeGreaterThanOrEqual(1);
    expect(api.assetUrl("asset-1", undefined, "proj-9")).toBe(
      "/api/projects/proj-9/assets/asset-1/file",
    );
  });

  it("returns empty only when ids are truly missing", () => {
    expect(api.assetUrl("")).toBe("");
    expect(api.assetUrl("asset-1")).toBe("");
    expect(api.assetUrl("asset-1", undefined, "")).toBe("");
  });

  it("uses bindAssetUrlProject when callers omit projectId", () => {
    api.bindAssetUrlProject("bound-proj");
    expect(api.assetUrl("asset-1")).toBe("/api/projects/bound-proj/assets/asset-1/file");
  });
});

describe("project-scoped unlock path", () => {
  it("extracts pid from project-scoped asset file URLs so fetch unlock header can attach", () => {
    const pid = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
    const aid = "aa000000-0000-4000-8000-000000000001";
    expect(projectIdFromApiPath(`/api/projects/${pid}/assets/${aid}/file`)).toBe(pid);
    expect(projectIdFromApiPath(`/api/assets/${aid}/file`)).toBe(null);
  });
});
