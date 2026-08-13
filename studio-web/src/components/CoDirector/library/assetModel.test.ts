import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * assetModel — pure-logic unit tests for resolveAssetUrl / getCardPreviewUrl.
 *
 * apiUrl() reads VITE_API_BASE at module load time, so we mock the apiBase
 * module to deterministically control the resolved base in each case.
 */

const MOCK_BASE = "https://api-beta.adeptui.org";

vi.mock("../../../runtime/apiBase", () => ({
  apiUrl: (path: string): string =>
    MOCK_BASE && path.startsWith("/") ? `${MOCK_BASE}${path}` : path,
}));

import { getCardPreviewUrl, resolveAssetUrl } from "./assetModel";

describe("resolveAssetUrl", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("resolves a relative /api path against the configured API_BASE", () => {
    expect(resolveAssetUrl("/api/assets/abc/thumb")).toBe(
      `${MOCK_BASE}/api/assets/abc/thumb`,
    );
  });

  it("returns a relative path unchanged when API_BASE is empty", async () => {
    vi.doMock("../../../runtime/apiBase", () => ({
      apiUrl: (path: string): string => path,
    }));
    const mod = await import("./assetModel");
    expect(mod.resolveAssetUrl("/api/assets/abc/thumb")).toBe(
      "/api/assets/abc/thumb",
    );
  });

  it("returns absolute https URLs unchanged", () => {
    expect(resolveAssetUrl("https://example.com/img.png")).toBe(
      "https://example.com/img.png",
    );
  });

  it("returns absolute http URLs unchanged", () => {
    expect(resolveAssetUrl("http://example.com/img.png")).toBe(
      "http://example.com/img.png",
    );
  });

  it("returns protocol-relative URLs unchanged", () => {
    expect(resolveAssetUrl("//example.com/img.png")).toBe(
      "//example.com/img.png",
    );
  });

  it("returns data: URIs unchanged", () => {
    const uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==";
    expect(resolveAssetUrl(uri)).toBe(uri);
  });

  it("returns undefined for undefined input", () => {
    expect(resolveAssetUrl(undefined)).toBeUndefined();
  });

  it("treats empty string as no URL (returns undefined)", () => {
    expect(resolveAssetUrl("")).toBeUndefined();
  });
});

describe("getCardPreviewUrl", () => {
  it("resolves thumb_url through resolveAssetUrl", () => {
    expect(
      getCardPreviewUrl({ id: "abc", thumb_url: "/api/assets/abc/thumb" }),
    ).toBe(`${MOCK_BASE}/api/assets/abc/thumb`);
  });

  it("resolves preview_url through resolveAssetUrl when no thumb_url", () => {
    expect(
      getCardPreviewUrl({ id: "abc", preview_url: "/api/assets/abc/preview" }),
    ).toBe(`${MOCK_BASE}/api/assets/abc/preview`);
  });

  it("resolves previewUrl (camelCase) through resolveAssetUrl", () => {
    expect(
      getCardPreviewUrl({ id: "abc", previewUrl: "/api/assets/abc/preview" }),
    ).toBe(`${MOCK_BASE}/api/assets/abc/preview`);
  });

  it("prefers thumb_url over preview_url", () => {
    expect(
      getCardPreviewUrl({
        id: "abc",
        thumb_url: "/api/assets/abc/thumb",
        preview_url: "/api/assets/abc/preview",
      }),
    ).toBe(`${MOCK_BASE}/api/assets/abc/thumb`);
  });

  it("passes absolute thumb_url through unchanged", () => {
    expect(
      getCardPreviewUrl({ id: "abc", thumb_url: "https://cdn.example.com/x.png" }),
    ).toBe("https://cdn.example.com/x.png");
  });

  it("passes data: thumb_url through unchanged", () => {
    const uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==";
    expect(getCardPreviewUrl({ id: "abc", thumb_url: uri })).toBe(uri);
  });

  it("returns undefined when no thumb/preview and not an image", () => {
    expect(getCardPreviewUrl({ id: "abc", kind: "video" })).toBeUndefined();
  });
});
