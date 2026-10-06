import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  clearPersistedTxt2VidPreviewAssetId,
  extractTxt2VidOutputAssetId,
  latestSuccessfulTxt2VidAssetId,
  persistTxt2VidPreviewAssetId,
  readPersistedTxt2VidPreviewAssetId,
  resolveTxt2VidPreviewAsset,
  txt2vidPreviewStorageKey,
} from "./txt2vidPreview";

const PROJECT = "proj-t2v";

beforeEach(() => {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
    },
  });
});

afterEach(() => {
  clearPersistedTxt2VidPreviewAssetId(PROJECT);
});

describe("txt2vidPreview", () => {
  it("extracts output_asset_id only from a successful txt2vid job", () => {
    expect(
      extractTxt2VidOutputAssetId({
        kind: "txt2vid",
        status: "done",
        params_json: JSON.stringify({ output_asset_id: "asset-1" }),
      }),
    ).toBe("asset-1");
    expect(
      extractTxt2VidOutputAssetId({
        kind: "txt2vid",
        status: "done",
        params_json: JSON.stringify({ outputAssetIds: ["asset-2"] }),
      }),
    ).toBe("asset-2");
  });

  it("does not replace preview from failed or cancelled jobs", () => {
    expect(
      extractTxt2VidOutputAssetId({
        kind: "txt2vid",
        status: "failed",
        params_json: JSON.stringify({ output_asset_id: "should-not-bind" }),
      }),
    ).toBeNull();
    expect(
      extractTxt2VidOutputAssetId({
        kind: "txt2vid",
        status: "cancelled",
        params_json: JSON.stringify({ output_asset_id: "should-not-bind" }),
      }),
    ).toBeNull();
    expect(
      extractTxt2VidOutputAssetId({
        kind: "txt2vid",
        status: "running",
        params_json: JSON.stringify({ output_asset_id: "should-not-bind" }),
      }),
    ).toBeNull();
  });

  it("ignores non-txt2vid jobs", () => {
    expect(
      extractTxt2VidOutputAssetId({
        kind: "render_scene",
        status: "done",
        params_json: JSON.stringify({ output_asset_id: "timeline-asset" }),
      }),
    ).toBeNull();
  });

  it("picks the newest successful txt2vid asset", () => {
    const id = latestSuccessfulTxt2VidAssetId([
      {
        kind: "txt2vid",
        status: "failed",
        params_json: JSON.stringify({ output_asset_id: "old-fail" }),
        updated_at: "2026-09-10T01:00:00",
        created_at: "2026-09-10T01:00:00",
      },
      {
        kind: "txt2vid",
        status: "done",
        params_json: JSON.stringify({ output_asset_id: "older" }),
        updated_at: "2026-09-10T02:00:00",
        created_at: "2026-09-10T02:00:00",
      },
      {
        kind: "txt2vid",
        status: "done",
        params_json: JSON.stringify({ output_asset_id: "newest" }),
        updated_at: "2026-09-10T03:00:00",
        created_at: "2026-09-10T03:00:00",
      },
    ]);
    expect(id).toBe("newest");
  });

  it("persists the active preview asset across reload", () => {
    expect(txt2vidPreviewStorageKey(PROJECT)).toBe("adept_txt2vid_preview_asset:proj-t2v");
    persistTxt2VidPreviewAssetId(PROJECT, "keep-me");
    expect(readPersistedTxt2VidPreviewAssetId(PROJECT)).toBe("keep-me");
  });

  it("resolves a project asset or a playable video stub", () => {
    const real = resolveTxt2VidPreviewAsset(
      PROJECT,
      [
        {
          id: "asset-1",
          project_id: PROJECT,
          tag: "clip",
          kind: "video",
          filename: "real.mp4",
          path: "C:/tmp/real.mp4",
          comfy_name: "studio/real.mp4",
          created_at: "2026-09-10",
        },
      ],
      "asset-1",
    );
    expect(real?.filename).toBe("real.mp4");
    const stub = resolveTxt2VidPreviewAsset(PROJECT, [], "pending-id");
    expect(stub?.id).toBe("pending-id");
    expect(stub?.kind).toBe("video");
    expect(resolveTxt2VidPreviewAsset(PROJECT, [], null)).toBeNull();
  });
});
