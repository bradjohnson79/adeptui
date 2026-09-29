import { describe, expect, it } from "vitest";
import { sceneWouldOverflow } from "./applySceneGenerator";
import type { TimelineBoardView } from "../components/DirectorTracks";
import type { Scene } from "../types";
import type { SceneTimelineMaster } from "./contracts";

const scene = { id: "s1", duration_sec: 30 } as Scene;

function timeline(promptLength: number): TimelineBoardView {
  return {
    duration_sec: 15,
    promptSegments: [],
    imageClips: [],
    videoClips: [],
    cameraClips: [],
    audioClips: [],
    sfxClips: [],
  } as unknown as TimelineBoardView;
}

function master(planned = 15, count = 1): SceneTimelineMaster {
  return {
    batchBlocks: Array.from({ length: count }, (_, index) => ({
      id: `b${index}`,
      duration: { plannedDuration: planned },
    })),
  } as unknown as SceneTimelineMaster;
}

describe("sceneWouldOverflow vs creative scene duration", () => {
  it("does not treat a 30s scene or 30s Timed Prompt as generator overflow", () => {
    expect(sceneWouldOverflow(timeline(30), master(15), scene, 15)).toBe(false);
  });

  it("still flags a single generation window planned past the native max", () => {
    expect(sceneWouldOverflow(timeline(8), master(30), scene, 15)).toBe(true);
  });
});
