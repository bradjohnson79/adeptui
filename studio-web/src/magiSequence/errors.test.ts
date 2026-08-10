import { describe, expect, it } from "vitest";
import {
  MAGI_ERROR_TAXONOMY,
  MagiApiError,
  describeMagiError,
  magiCanonicalCode,
  magiErrorFromResponse,
  magiErrorInfo,
} from "./errors";

describe("MAGI error taxonomy", () => {
  it("resolves legacy lowercase codes to canonical uppercase codes", () => {
    expect(magiCanonicalCode("revision_conflict")).toBe("REVISION_CONFLICT");
    expect(magiCanonicalCode("validation_failed")).toBe("INVALID_SEQUENCE");
    expect(magiCanonicalCode("clips_required")).toBe("CLIPS_REQUIRED");
    expect(magiCanonicalCode("asset_ownership")).toBe("ASSET_OWNERSHIP");
    expect(magiCanonicalCode("REVISION_CONFLICT")).toBe("REVISION_CONFLICT");
  });

  it("returns canonical info for known codes", () => {
    const info = magiErrorInfo("REVISION_CONFLICT");
    expect(info.kind).toBe("conflict");
    expect(info.status).toBe(409);
    expect(info.recovery).toBeTruthy();
    expect(info.message).toMatch(/changed on the server/);
  });

  it("declares CLIP_NOT_FOUND as a genuine not-found (404)", () => {
    const info = magiErrorInfo("CLIP_NOT_FOUND");
    expect(info.kind).toBe("not_found");
    expect(info.status).toBe(404);
    expect(info.recovery).toBeTruthy();
  });

  it("declares SEQUENCE_NOT_FOUND as latent", () => {
    const info = magiErrorInfo("SEQUENCE_NOT_FOUND");
    expect(info.kind).toBe("latent");
  });

  it("falls back to UNKNOWN for unrecognized codes without leaking raw detail", () => {
    const info = magiErrorInfo("SOME_RANDOM_INTERNAL_CODE");
    expect(info.code).toBe("SOME_RANDOM_INTERNAL_CODE");
    expect(info.message).toMatch(/unexpected error/);
  });

  it("parses the MAGI error envelope from a failed response", async () => {
    const res = {
      status: 409,
      json: async () => ({
        detail: {
          error: { code: "revision_conflict", message: "Changed on server." },
        },
      }),
    } as unknown as Response;
    const info = await magiErrorFromResponse(res);
    expect(info.status).toBe(409);
    expect(info.message).toBe("Changed on server.");
    expect(info.recovery).toBeTruthy();
  });

  it("falls back to taxonomy defaults for non-JSON failure bodies", async () => {
    const res = { status: 502, json: async () => { throw new Error("boom"); } } as unknown as Response;
    const info = await magiErrorFromResponse(res);
    expect(info.status).toBe(502);
    expect(info.message).toMatch(/unexpected error/);
  });

  it("describeMagiError never returns a stack trace", () => {
    const apiError = new MagiApiError(magiErrorInfo("CLIP_NOT_FOUND"));
    const msg = describeMagiError(apiError);
    expect(msg).toContain("does not contain the referenced clip");
    expect(msg).not.toMatch(/at /);
    expect(describeMagiError(new Error("plain message"))).toBe("plain message");
    expect(describeMagiError({ some: "object" })).toMatch(/unexpected error/);
  });

  it("every canonical backend code has a taxonomy entry", () => {
    for (const code of [
      "INVALID_SEQUENCE",
      "INVALID_REVISION",
      "REVISION_CONFLICT",
      "INVALID_CLIP_ASSET",
      "ASSET_NOT_FOUND",
      "ASSET_PROJECT_MISMATCH",
      "ASSET_OWNERSHIP",
      "ASSET_ID_REQUIRED",
      "CLIPS_REQUIRED",
      "CLIP_NOT_FOUND",
      "SCENE_NOT_FOUND",
      "BATCH_NOT_FOUND",
      "SEQUENCE_NOT_FOUND",
      "PERSISTENCE_FAILED",
      "RENDER_FAILED",
      "OVERLAY_NOT_FOUND",
      "OVERLAY_INVALID",
      "IMPORT_FAILED",
      "EXPORT_FAILED",
      "TIMELINE_HANDOFF_FAILED",
      "UNSUPPORTED_OPERATION",
    ]) {
      expect(MAGI_ERROR_TAXONOMY[code], code).toBeDefined();
    }
  });
});
