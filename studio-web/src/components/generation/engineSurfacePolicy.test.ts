import { describe, expect, it } from "vitest";
import { currentWorkspaceSurface, decideEngineOnSurface } from "./engineSurfacePolicy";

describe("engineSurfacePolicy", () => {
  it("hides unsupported engines on Text to Video when workflow authority says unsupported", () => {
    const unsupported = decideEngineOnSurface({
      engine: "seedance-2.0",
      surface: "text-to-video",
      executable: true,
      supportsTextToVideo: false,
      requiresLastFrame: false,
      workflowCapability: { supported: false, executable: false, reason: "No T2V workflow" },
    });
    expect(unsupported.visible).toBe(false);
    expect(unsupported.disabled).toBe(true);
  });

  it("shows local LTX 2.5 and MiniMax on Text to Video when they support T2V", () => {
    const ltx25 = decideEngineOnSurface({
      engine: "ltx-2.5",
      surface: "text-to-video",
      executable: true,
      supportsTextToVideo: true,
      requiresLastFrame: false,
    });
    expect(ltx25.visible).toBe(true);
    expect(ltx25.disabled).toBe(false);
    const h3 = decideEngineOnSurface({
      engine: "minimax-h3",
      surface: "text-to-video",
      executable: true,
      supportsTextToVideo: true,
      requiresLastFrame: false,
    });
    expect(h3.visible).toBe(true);
    expect(h3.disabled).toBe(false);
  });

  it("keeps hosted Seedance 2.0 and 2.5 on Text to Video when executable", () => {
    for (const engine of ["seedance-2.0", "seedance-2.5"] as const) {
      const seedance = decideEngineOnSurface({
        engine,
        surface: "text-to-video",
        executable: true,
        supportsTextToVideo: true,
        requiresLastFrame: false,
      });
      expect(seedance.visible).toBe(true);
      expect(seedance.disabled).toBe(false);
    }
  });

  it("hides Seedance versions on 3 Frame without a three-still workflow", () => {
    const seedance = decideEngineOnSurface({
      engine: "seedance-2.5",
      surface: "three-frame",
      executable: true,
      supportsTextToVideo: true,
      requiresLastFrame: false,
    });
    expect(seedance.visible).toBe(false);
  });

  it("keeps MiniMax and LTX 2.5 selectable on 1 Frame from I2V workflow truth", () => {
    const h3 = decideEngineOnSurface({
      engine: "minimax-h3",
      surface: "one-frame",
      executable: false,
      supportsTextToVideo: false,
      requiresLastFrame: false,
      disabledReason: "Timeline reference-to-video only",
      workflowCapability: {
        supported: true,
        executable: true,
        readiness: "Available on demand",
        reason: "",
      },
    });
    expect(h3.visible).toBe(true);
    expect(h3.disabled).toBe(false);
    const ltx25 = decideEngineOnSurface({
      engine: "ltx-2.5",
      surface: "one-frame",
      executable: false,
      supportsTextToVideo: false,
      requiresLastFrame: false,
      workflowCapability: {
        supported: true,
        executable: true,
        readiness: "Ready",
        reason: "",
      },
    });
    expect(ltx25.visible).toBe(true);
    expect(ltx25.disabled).toBe(false);
  });

  it("does not gray MiniMax/LTX 2.5 on 1 Frame when Timeline executable is false and workflow records have not arrived", () => {
    const h3 = decideEngineOnSurface({
      engine: "minimax-h3",
      surface: "one-frame",
      executable: false,
      supportsTextToVideo: false,
      requiresLastFrame: false,
    });
    expect(h3.visible).toBe(true);
    expect(h3.disabled).toBe(false);
    expect(h3.reason).not.toMatch(/Unsupported in this workflow/i);
  });

  it("does not mark LTX 2.5 Ready on 3 Frame from ordinary I2V", () => {
    const ltx25 = decideEngineOnSurface({
      engine: "ltx-2.5",
      surface: "three-frame",
      executable: false,
      supportsTextToVideo: false,
      requiresLastFrame: false,
    });
    expect(ltx25.visible).toBe(true);
    expect(ltx25.disabled).toBe(true);
    expect(ltx25.reason).toMatch(/first \+ last/i);
  });

  it("maps workspace query to surface", () => {
    expect(currentWorkspaceSurface("?workspace=txt2vid")).toBe("text-to-video");
    expect(currentWorkspaceSurface("?workspace=one")).toBe("one-frame");
    expect(currentWorkspaceSurface("?workspace=three")).toBe("three-frame");
    expect(currentWorkspaceSurface("?workspace=timeline")).toBe("timeline");
  });

  it("enables MiniMax H3 on 3 Frame for proven local first+last / AddGuide", () => {
    const h3 = decideEngineOnSurface({
      engine: "minimax-h3",
      surface: "three-frame",
      executable: false,
      supportsTextToVideo: false,
      requiresLastFrame: false,
    });
    expect(h3.visible).toBe(true);
    expect(h3.disabled).toBe(false);
  });
});
