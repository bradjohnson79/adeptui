import { describe, expect, it } from "vitest";
import {
  H3_NATIVE_GENERATION_SEC,
  SCENE_DURATION_AUTHORITY,
  canonicalSceneDurationSec,
  decideTimedPromptRange,
  h3ExtensionWindows,
  liveSceneClockSec,
  sanitizeSceneDurationSec,
} from "./sceneDurationAuthority";

describe("scene duration authority", () => {
  it("names Scene.duration_sec as the creative clock", () => {
    expect(SCENE_DURATION_AUTHORITY).toBe("Scene.duration_sec");
    expect(H3_NATIVE_GENERATION_SEC).toBe(15);
  });

  it("prefers Scene.duration_sec over a leftover timeline clock", () => {
    expect(canonicalSceneDurationSec({ duration_sec: 30 }, { duration_sec: 15 })).toBe(30);
    expect(canonicalSceneDurationSec({ duration_sec: 0 }, { duration_sec: 12 })).toBe(12);
  });

  it("uses the longer live clock while Scene hydration lags", () => {
    expect(liveSceneClockSec({ duration_sec: 15 }, { duration_sec: 30 })).toBe(30);
  });

  it("allows any positive scene length — no 15/20/30 product cap", () => {
    expect(sanitizeSceneDurationSec(30).ok).toBe(true);
    expect(sanitizeSceneDurationSec(52).ok).toBe(true);
    expect(sanitizeSceneDurationSec(180).ok).toBe(true);
    expect(sanitizeSceneDurationSec(0).ok).toBe(false);
    expect(sanitizeSceneDurationSec(-4).ok).toBe(false);
  });

  it("plans H3 continuation windows from scene duration, not a native 30s request", () => {
    expect(h3ExtensionWindows(15)).toEqual([{ start: 0, end: 15 }]);
    expect(h3ExtensionWindows(30)).toEqual([
      { start: 0, end: 15 },
      { start: 15, end: 30 },
    ]);
    expect(h3ExtensionWindows(37)).toEqual([
      { start: 0, end: 15 },
      { start: 15, end: 30 },
      { start: 30, end: 37 },
    ]);
  });

  it("allows a Timed Prompt that fits the scene", () => {
    expect(decideTimedPromptRange(0, 30, 30)).toEqual({ ok: true });
  });

  it("rejects a Timed Prompt that overruns the scene and offers an explicit extend", () => {
    const decision = decideTimedPromptRange(0, 30, 15, "Scene 1");
    expect(decision.ok).toBe(false);
    if (decision.ok) return;
    expect(decision.reason).toBe("overflow");
    expect(decision.neededSceneSec).toBe(30);
    expect(decision.message).toContain("15-second scene");
    expect(decision.message).toContain("Extend Scene 1 to 30 seconds?");
  });
});
