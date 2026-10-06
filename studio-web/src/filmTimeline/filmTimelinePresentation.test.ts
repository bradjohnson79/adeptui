import { describe, expect, it } from "vitest";
import {
  displayLtxMode,
  filmTimelineRenderHud,
  filmTimelineRenderLine,
  foldLegacyProductionSelection,
  LTX_TIMELINE_GENERATOR_ID,
  renderNoticeForSegments,
  resolveFilmTimelinePlanDims,
  visibleRenderNotice,
  visibleSegmentError,
} from "./filmTimelinePresentation";

describe("legacy production fold", () => {
  it("reads old production ids as LTX 2.5 plus a mode", () => {
    expect(foldLegacyProductionSelection("text-to-video", "")).toEqual({
      modelId: LTX_TIMELINE_GENERATOR_ID,
      ltxMode: "text",
    });
    expect(foldLegacyProductionSelection("one-frame", "")).toEqual({
      modelId: LTX_TIMELINE_GENERATOR_ID,
      ltxMode: "one_frame",
    });
    expect(foldLegacyProductionSelection("three-frame", "")).toEqual({
      modelId: LTX_TIMELINE_GENERATOR_ID,
      ltxMode: "three_frame",
    });
    expect(foldLegacyProductionSelection(LTX_TIMELINE_GENERATOR_ID, "start_end").modelId).toBe(LTX_TIMELINE_GENERATOR_ID);
  });

  it("shows a stored third frame as Start Frame only when a start image exists", () => {
    expect(displayLtxMode("text-to-video", "")).toBe("text");
    expect(displayLtxMode("one-frame", "")).toBe("one_frame");
    expect(displayLtxMode("start_end", "end-only")).toBe("start_end");
    expect(displayLtxMode("three_frame", "start-id")).toBe("one_frame");
    expect(displayLtxMode("three_frame", "")).toBe("text");
  });
});

describe("render notices", () => {
  it("dismisses the same polled notice and shows a new event", () => {
    const completed = renderNoticeForSegments([{ id: "seg-a", status: "completed" }]);
    expect(completed).toEqual({ key: "seg-a:completed", status: "completed", text: "Render complete" });
    expect(visibleRenderNotice(completed, "seg-a:completed")).toBeNull();
    expect(visibleRenderNotice(renderNoticeForSegments([{ id: "seg-a", status: "completed" }]), "seg-a:completed")).toBeNull();
    const cancelled = renderNoticeForSegments([
      { id: "seg-a", status: "completed" },
      { id: "seg-b", status: "cancelled" },
    ]);
    expect(visibleRenderNotice(cancelled, "seg-a:completed")?.text).toBe("Render cancelled");
    const failed = renderNoticeForSegments([{ id: "seg-c", status: "failed", error: "The render stopped." }]);
    expect(failed?.text).toBe("The render stopped.");
  });
});

describe("render status HUD", () => {
  const segments = (
    status: string,
    extra?: { progress?: number; progressGrounded?: boolean; phaseLabel?: string; elapsedSec?: number; error?: string },
  ) => [
    {
      id: "seg-a",
      order: 0,
      status,
      error: extra?.error,
      generationMetadata: {
        renderStatus: {
          progress: extra?.progress,
          progressGrounded: extra?.progressGrounded,
          phaseLabel: extra?.phaseLabel,
          elapsedSec: extra?.elapsedSec,
          status,
        },
      },
    },
  ];

  it("shows a grounded percent on one shared line", () => {
    const hud = filmTimelineRenderHud({
      segments: segments("generating", { progress: 0.42, progressGrounded: true, phaseLabel: "Generating", elapsedSec: 48 }),
      modelLabel: "MiniMax H3 — Local",
      sceneName: "Scene 1",
      shotName: "Shot 01",
    });
    expect(hud?.percent).toBe(42);
    expect(hud?.headline).toBe("Generating — 42%");
    expect(filmTimelineRenderLine(hud!)).toBe(hud?.headline);
    expect(hud?.elapsed).toBe("00:48");
    expect(hud?.model).toBe("MiniMax H3 — Local");
    expect(hud?.bar).toBe("live");
  });

  it("holds the last percent while preparing and does not claim a rise", () => {
    const hud = filmTimelineRenderHud({
      segments: segments("generating", { progress: 0.2, progressGrounded: false, phaseLabel: "Preparing model" }),
    });
    expect(hud?.headline).toBe("Preparing model...");
    expect(hud?.headline.includes("%")).toBe(false);
    expect(hud?.percent).toBe(20);
    expect(hud?.bar).toBe("held");
    expect(filmTimelineRenderLine(hud!)).toBe("Preparing model... 20%");
  });

  it("does not invent a percent when none was stored", () => {
    const hud = filmTimelineRenderHud({
      segments: segments("generating", { progressGrounded: false, phaseLabel: "Preparing model" }),
    });
    expect(hud?.percent).toBeNull();
    expect(hud?.bar).toBe("wait");
    expect(filmTimelineRenderLine(hud!)).toBe("Preparing model...");
  });

  it("names the in-flight segment by its stored shot number", () => {
    const hud = filmTimelineRenderHud({
      segments: [
        { id: "a", order: 0, status: "completed", shotNumber: 1 },
        {
          id: "b",
          order: 1,
          status: "generating",
          shotNumber: 2,
          generationMetadata: { renderStatus: { progress: 0.54, progressGrounded: true, phaseLabel: "Generating" } },
        },
        { id: "c", order: 2, status: "empty", shotNumber: 3 },
      ],
      sceneName: "Scene 28",
      shotName: "Shot 1",
    });
    expect(hud?.headline).toBe("Generating Shot 2 — 54%");
    expect(hud?.place).toBe("Scene 28 — Shot 2");
  });

  it("names a Re-Take by the shot it is replacing", () => {
    const hud = filmTimelineRenderHud({
      segments: [
        { id: "a", order: 0, status: "completed", shotNumber: 4 },
        {
          id: "b",
          order: 1,
          status: "generating",
          shotNumber: 5,
          generationMetadata: {
            retakePreviousAssetId: "current-shot-5",
            renderStatus: { progress: 0.17, progressGrounded: true, phaseLabel: "Generating" },
          },
        },
      ],
      sceneName: "Scene 28",
      shotName: "Shot 1",
    });
    expect(hud?.headline).toBe("Re-Taking Shot 5 — 17%");
    expect(hud?.place).toBe("Scene 28 — Shot 5");
  });

  it("replaces a frozen percent with the initialization stall sentence", () => {
    const hud = filmTimelineRenderHud({
      segments: [
        {
          id: "b",
          order: 1,
          status: "generating",
          shotNumber: 5,
          generationMetadata: {
            renderStatus: {
              progressGrounded: false,
              phaseLabel: "Generation stalled during model initialization.",
            },
          },
        },
      ],
    });
    expect(hud?.headline).toBe("Generation stalled during model initialization.");
    expect(hud?.percent).toBeNull();
  });

  it("falls back to segment position only when no shot number is stored", () => {
    const hud = filmTimelineRenderHud({
      segments: [
        { id: "a", order: 0, status: "completed" },
        {
          id: "b",
          order: 1,
          status: "generating",
          generationMetadata: { renderStatus: { progress: 0.54, progressGrounded: true, phaseLabel: "Generating" } },
        },
        { id: "c", order: 2, status: "empty" },
      ],
    });
    expect(hud?.headline).toBe("Generating segment 2/3 — 54%");
  });

  it("names a finished shot on the completion line", () => {
    const hud = filmTimelineRenderHud({
      segments: [{ id: "b", order: 1, status: "completed", shotNumber: 2 }],
      shotName: "Shot 2",
      showComplete: true,
    });
    expect(hud?.headline).toBe("Shot 2 complete — 100%");
  });

  it("uses stitch status only when a stitch is actually running", () => {
    expect(filmTimelineRenderHud({ segments: [{ id: "a", status: "completed" }], stitchStatus: "ready" })).toBeNull();
    expect(filmTimelineRenderHud({ segments: [{ id: "a", status: "completed" }], stitchStatus: "stale" })).toBeNull();
    expect(filmTimelineRenderHud({ segments: [{ id: "a", status: "completed" }], stitchStatus: "stitching" })?.headline).toBe("Stitching scene…");
  });

  it("clears the percent on cancel and failure", () => {
    const cancelled = filmTimelineRenderHud({
      segments: segments("cancelled", { progress: 0.9, progressGrounded: true, phaseLabel: "Generating" }),
      showTerminal: true,
    });
    expect(cancelled?.headline).toBe("Render cancelled");
    expect(cancelled?.percent).toBeNull();
    const failed = filmTimelineRenderHud({
      segments: segments("failed", { progress: 0.9, progressGrounded: true, error: "Sampling step 13/25 node 10 fps_mode" }),
      showTerminal: true,
    });
    expect(failed?.headline).toBe("Render failed");
    expect(failed?.percent).toBeNull();
    expect(failed?.detail).toBe("");
    expect(filmTimelineRenderHud({
      segments: segments("failed", { error: "The render stopped." }),
      showTerminal: true,
    })?.detail).toBe("The render stopped.");
  });

  it("shows completion at 100 percent only while the brief hold is on", () => {
    const done = segments("completed");
    expect(filmTimelineRenderHud({ segments: done, showComplete: true })?.headline).toBe("Render complete — 100%");
    expect(filmTimelineRenderHud({ segments: done, showComplete: true })?.percent).toBe(100);
    expect(filmTimelineRenderHud({ segments: done, showComplete: false })).toBeNull();
    expect(renderNoticeForSegments([{ id: "seg-a", status: "completed" }])?.text).toBe("Render complete");
  });

  it("rejects internal ids, step counts, and broken encoding", () => {
    const hud = filmTimelineRenderHud({
      segments: segments("generating", { progress: 0.4, progressGrounded: true, phaseLabel: "Sampling step 10/25" }),
      modelLabel: "minimax-h3-i2v-local",
      sceneName: "Scene Â· 1",
      shotName: "job 8f3c2a10-1111-4222-8333-444444444444",
    });
    const shown = `${hud?.headline} ${hud?.model} ${hud?.place} ${filmTimelineRenderLine(hud!)}`;
    expect(shown).not.toMatch(/fps_mode|node|step|Â|minimax-h3|8f3c2a10/i);
    expect(hud?.headline).toBe("Generating — 40%");
  });
});

describe("visibleSegmentError", () => {
  it("shows the raw sticky failure until settings change suppresses it", () => {
    expect(visibleSegmentError("H3_DIRECTOR_REFS_REQUIRED: needs a character picture", false)).toBe(
      "H3_DIRECTOR_REFS_REQUIRED: needs a character picture",
    );
    expect(visibleSegmentError("H3_DIRECTOR_REFS_REQUIRED: needs a character picture", true)).toBe("");
    expect(visibleSegmentError("", true)).toBe("");
  });

  it("hides legacy R2V duration sticky copy when Director path opts in", () => {
    const legacy =
      "MiniMax H3 Reference-to-Video needs a frame count where n ≡ 5 (mod 17). 14s at 24 fps is 336 frames. Adept will not pad the clip.";
    expect(visibleSegmentError(legacy, false)).toBe(legacy);
    expect(visibleSegmentError(legacy, false, { hideLegacyR2v: true })).toBe("");
  });
});

describe("resolveFilmTimelinePlanDims", () => {
  it("prefers stamped segment resolvedGeneration over Scene canvas", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      segments: [{ generationMetadata: { resolvedGeneration: { width: 1152, height: 640 } } }],
    });
    expect(dims).toEqual({ width: 1152, height: 640, source: "resolvedGeneration" });
  });

  it("falls back to H3 Auto Quality 0.7 → 1152×640 when nothing is stamped", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      h3Resolution: { mode: "auto", megapixels: 0.7 },
    });
    expect(dims).toEqual({ width: 1152, height: 640, source: "h3_auto_quality" });
  });

  it("is aspect-aware for H3 manual 1.2 MP (21:9 → 1728×736)", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      h3Resolution: { mode: "manual", megapixels: 1.2 },
      aspect: "21:9",
    });
    expect(dims).toEqual({ width: 1728, height: 736, source: "h3_auto_quality" });
  });

  it("defaults to 16:9 when no aspect is given (1.2 MP → 1504×832)", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      h3Resolution: { mode: "manual", megapixels: 1.2 },
    });
    expect(dims).toEqual({ width: 1504, height: 832, source: "h3_auto_quality" });
  });

  it("does not invent H3 dims for non-H3 generators", () => {
    expect(resolveFilmTimelinePlanDims({ generatorId: "ltx-25-local" })).toBeNull();
  });

  it("returns no plan dims for an H3 shape outside H3_SUPPORTED_ASPECTS (never 16:9)", () => {
    // The backend fail-closes on these shapes; showing 16:9-class dims would be
    // a display the backend refuses (legal_canvas.require_h3_timeline_aspect).
    for (const aspect of ["3:2", "16:10", "18:9", "2.39:1", "5:4"]) {
      expect(
        resolveFilmTimelinePlanDims({
          generatorId: "minimax-h3-i2v-local",
          h3Resolution: { mode: "auto", megapixels: 0.7 },
          aspect,
        }),
      ).toBeNull();
    }
  });

  it("keeps the certified Auto 0.7 fallback for supported H3 shapes and aliases", () => {
    const base = { generatorId: "minimax-h3-i2v-local", h3Resolution: { mode: "auto" as const, megapixels: 0.7 } };
    expect(resolveFilmTimelinePlanDims({ ...base, aspect: "16:9" })).toEqual({
      width: 1152,
      height: 640,
      source: "h3_auto_quality",
    });
    expect(resolveFilmTimelinePlanDims({ ...base, aspect: "≈16:9" })).toEqual({
      width: 1152,
      height: 640,
      source: "h3_auto_quality",
    });
    expect(resolveFilmTimelinePlanDims({ ...base, aspect: "1:1" })).toEqual({
      width: 864,
      height: 864,
      source: "h3_auto_quality",
    });
  });

  it("still prefers stamped dims over refusing an unsupported shape", () => {
    // Stamped resolvedGeneration is observed reality, not a guess.
    expect(
      resolveFilmTimelinePlanDims({
        generatorId: "minimax-h3-i2v-local",
        segments: [{ generationMetadata: { resolvedGeneration: { width: 1728, height: 736 } } }],
        aspect: "3:2",
      }),
    ).toEqual({ width: 1728, height: 736, source: "resolvedGeneration" });
  });
});
