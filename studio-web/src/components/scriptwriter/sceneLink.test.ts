import { describe, expect, it } from "vitest";
import { resolveLinkSceneId } from "./sceneLink";
import type { Scene } from "../../types";

/**
 * CDX-058: linkScene must bind the SELECTED project scene (not project.scenes[0]).
 */

function scene(id: string, name = `Scene ${id}`): Scene {
  return {
    id,
    project_id: "proj",
    index: 0,
    name,
    engine: "minimax-h3",
    prompt: "",
    duration_sec: 5,
    lipsync_enabled: false,
    camera_note: "",
    seed: 1,
  } as Scene;
}

describe("resolveLinkSceneId", () => {
  const scenes = [scene("scene-1", "Opening"), scene("scene-2", "Climax"), scene("scene-3", "Ending")];

  it("returns the explicitly selected scene id", () => {
    expect(resolveLinkSceneId(scenes, "scene-2")).toBe("scene-2");
  });

  it("does not let the creator link to a scene the project no longer has", () => {
    // Selection pointing at a removed scene falls back to the first scene.
    expect(resolveLinkSceneId(scenes, "scene-gone")).toBe("scene-1");
  });

  it("defaults to the first scene when nothing is selected (historical behavior)", () => {
    expect(resolveLinkSceneId(scenes, undefined)).toBe("scene-1");
    expect(resolveLinkSceneId(scenes, null)).toBe("scene-1");
    expect(resolveLinkSceneId(scenes, "")).toBe("scene-1");
  });

  it("returns undefined only when the project has no scenes", () => {
    expect(resolveLinkSceneId([], "scene-1")).toBeUndefined();
    expect(resolveLinkSceneId([], undefined)).toBeUndefined();
  });

  it("never returns the first scene when the creator picked a later one", () => {
    // Regression guard for the scenes[0] hardcode: choosing scene 2 or 3 must
    // keep that exact id (linkScene sends it to the backend).
    expect(resolveLinkSceneId(scenes, "scene-3")).toBe("scene-3");
    expect(resolveLinkSceneId(scenes, "scene-2")).not.toBe("scene-1");
  });
});
