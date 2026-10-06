import { describe, expect, it } from "vitest";
import {
  SCENE_NAME_MAX,
  isSceneDeleteAlreadyGone,
  neighborSceneId,
  normalizeSceneName,
} from "./sceneLifecycle";

describe("normalizeSceneName", () => {
  it("trims surrounding whitespace", () => {
    expect(normalizeSceneName("  Venture Corridor Walk  ")).toEqual({
      ok: true,
      name: "Venture Corridor Walk",
    });
  });

  it("rejects empty and whitespace-only names", () => {
    expect(normalizeSceneName("")).toEqual({ ok: false, reason: "Enter a scene name." });
    expect(normalizeSceneName("   ")).toEqual({ ok: false, reason: "Enter a scene name." });
  });

  it("respects the existing 200-character database limit", () => {
    const ok = "A".repeat(SCENE_NAME_MAX);
    const over = "A".repeat(SCENE_NAME_MAX + 1);
    expect(normalizeSceneName(ok)).toEqual({ ok: true, name: ok });
    expect(normalizeSceneName(over).ok).toBe(false);
  });
});

describe("neighborSceneId", () => {
  const ids = ["scene-1", "dialogue", "walk"];

  it("prefers the next scene in current ordering", () => {
    expect(neighborSceneId(ids, "scene-1")).toBe("dialogue");
    expect(neighborSceneId(ids, "dialogue")).toBe("walk");
  });

  it("falls back to the previous scene when removing the last", () => {
    expect(neighborSceneId(ids, "walk")).toBe("dialogue");
  });

  it("returns undefined when the last remaining scene is removed", () => {
    expect(neighborSceneId(["only"], "only")).toBeUndefined();
  });
});

describe("isSceneDeleteAlreadyGone", () => {
  it("treats 404 / SCENE_NOT_FOUND as already deleted", () => {
    expect(isSceneDeleteAlreadyGone({ status: 404, code: "SCENE_NOT_FOUND" })).toBe(true);
    expect(isSceneDeleteAlreadyGone({ status: 500 })).toBe(false);
  });
});
