import { describe, expect, it } from "vitest";
import {
  DEFAULT_NEW_SCENE_SEC,
  LTX_NEW_SCENE_SEC,
  MINIMAX_H3_NEW_SCENE_SEC,
  defaultNewSceneDurationSec,
  nextLocalSceneDurationSec,
} from "./timelineSceneDuration";

describe("nextLocalSceneDurationSec", () => {
  it("seeds new MiniMax H3 Timeline scenes at 15s (creator fidelity = H3 max), not 12 or legacy 8", () => {
    expect(MINIMAX_H3_NEW_SCENE_SEC).toBe(15);
    const next = nextLocalSceneDurationSec(undefined, { engine: "minimax-h3" });
    expect(next.ok).toBe(true);
    expect(next.durationSec).toBe(15);
    expect(next.durationSec).not.toBe(12);
    expect(next.durationSec).not.toBe(8);
  });

  it("seeds LTX 2.5 Timeline scenes at exactly 20s", () => {
    expect(LTX_NEW_SCENE_SEC).toBe(20);
    expect(defaultNewSceneDurationSec("ltx-2.5")).toBe(20);
    expect(defaultNewSceneDurationSec("ltx-2.5-distilled")).toBe(20);
    const next = nextLocalSceneDurationSec(undefined, { engine: "ltx-2.5" });
    expect(next.ok).toBe(true);
    expect(next.durationSec).toBe(20);
  });

  it("keeps non-H3/non-LTX fallback at DEFAULT_NEW_SCENE_SEC when no capability max is supplied", () => {
    expect(DEFAULT_NEW_SCENE_SEC).toBe(12);
    const next = nextLocalSceneDurationSec(undefined, { engine: "wan" });
    expect(next.ok).toBe(true);
    expect(next.durationSec).toBe(DEFAULT_NEW_SCENE_SEC);
  });

  it("lets non-H3/non-LTX generators keep their own defaults via capability max", () => {
    expect(defaultNewSceneDurationSec("wan", 8)).toBe(8);
    const next = nextLocalSceneDurationSec(undefined, { engine: "wan", maxDurationSec: 8 });
    expect(next.ok).toBe(true);
    expect(next.durationSec).toBe(8);
  });

  it("allows a new scene even when other scenes already exceed 20s total", () => {
    const next = nextLocalSceneDurationSec(undefined, { engine: "minimax-h3" });
    expect(next.ok).toBe(true);
    expect(next.durationSec).toBe(MINIMAX_H3_NEW_SCENE_SEC);
  });

  it("does not use a project-total remainder of zero", () => {
    expect(nextLocalSceneDurationSec(undefined, { engine: "minimax-h3" }).reason).toBeUndefined();
  });

  it("seeds blank/missing engine as H3 (product default resolves to H3)", () => {
    expect(nextLocalSceneDurationSec(undefined, { engine: "" }).durationSec).toBe(15);
    expect(nextLocalSceneDurationSec(undefined, { engine: null }).durationSec).toBe(15);
    expect(nextLocalSceneDurationSec(undefined, { engine: undefined }).durationSec).toBe(15);
  });

  it('seeds the legal EngineName "auto" as H3 — it resolves to H3 at generation time', () => {
    // Regression: "auto" previously fell through to DEFAULT_NEW_SCENE_SEC (12.0 symptom).
    expect(nextLocalSceneDurationSec(undefined, { engine: "auto" }).durationSec).toBe(15);
    expect(nextLocalSceneDurationSec(undefined, { engine: "Auto" }).durationSec).toBe(15);
    expect(nextLocalSceneDurationSec(undefined, { engine: " auto " }).durationSec).toBe(15);
  });

  it("seeds any minimax-h3* variant as H3", () => {
    expect(nextLocalSceneDurationSec(undefined, { engine: "minimax-h3-i2v-local" }).durationSec).toBe(15);
    expect(nextLocalSceneDurationSec(undefined, { engine: "MiniMax-H3" }).durationSec).toBe(15);
  });

  it("respects a lower per-call cap without inventing a second default", () => {
    const next = nextLocalSceneDurationSec(10, { engine: "minimax-h3" });
    expect(next.ok).toBe(true);
    expect(next.durationSec).toBe(10);
  });
});
