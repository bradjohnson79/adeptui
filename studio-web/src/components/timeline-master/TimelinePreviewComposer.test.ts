import { describe, expect, it } from "vitest";
import type { Asset, Job, Project, Scene } from "../types";
import { resolvePreviewComposition } from "./TimelinePreviewComposer";
import type { DirectorSelection } from "../../directorSelection";

const baseScene: Scene = {
  id: "s1",
  name: "Scene 1",
  prompt: "",
  duration_sec: 5,
  fps: 24,
  fps_mode: "auto",
  engine: "minimax-h3",
  output_path: null,
  lipsync_output_path: null,
  start_asset_id: null,
  aspect_ratio: "16:9",
  director_json: null,
  status: "draft",
} as unknown as Scene;

const baseProject = { id: "p1" } as unknown as Project;

const nullSelection: DirectorSelection = { kind: null };

function makeJob(overrides: Partial<Job>): Job {
  return { id: "j1", project_id: "p1", scene_id: "s1", status: "running", ...overrides } as Job;
}

function makeAsset(overrides: Partial<Asset>): Asset {
  return {
    id: "a1",
    project_id: "p1",
    kind: "image",
    filename: "img.png",
    tag: "tag",
    ...overrides,
  } as Asset;
}

describe("resolvePreviewComposition (PREVIEW_COMPOSER_IS_SOLE_SOURCE_OF_TRUTH)", () => {
  it("returns idle when nothing is active", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: null,
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("idle");
  });

  it("library asset takes precedence over generation and final output", () => {
    const c = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "/out.mp4" },
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: makeAsset({ id: "lib", kind: "image" }),
      activeJob: makeJob({ status: "running" }),
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("library");
    if (c.kind === "library") expect(c.mediaKind).toBe("image");
  });

  it("returns failed when active job failed", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "failed" }),
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("failed");
  });

  it("returns final_output when job is done", () => {
    const c = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "/out.mp4" },
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "done" }),
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("final_output");
    if (c.kind === "final_output") expect(c.mediaKind).toBe("video");
  });

  it("returns generation_draft while job running", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "running" }),
      preview: { sourceUrl: "/preview.mp4" },
    });
    expect(c.kind).toBe("generation_draft");
  });

  it("returns preparing when stage is 'preparing' and no preview yet", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "running", stage: "preparing assets" }),
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("preparing");
  });

  it("returns final_output (no job) when scene has output_path", () => {
    const c = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "/out.mp4" },
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: null,
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("final_output");
  });

  it("library audio is classified correctly", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: makeAsset({ id: "aud", kind: "audio", filename: "voice.mp3" }),
      activeJob: null,
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("library");
    if (c.kind === "library") expect(c.mediaKind).toBe("audio");
  });

  it("returns timeline_frame when playhead intersects an image clip and no generation/output", () => {
    const timeline = {
      media_mode: "image",
      duration_sec: 5,
      image_clips: [
        { id: "ic1", asset_id: "ast1", start: 0, length: 3, label: "Shot A", role: "guide" },
      ],
      video_clips: [],
      prompt_segments: [
        { id: "ps1", start: 0, length: 3, text: "A lone figure on a ridge", weight: 1 },
      ],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 1,
      guidance_priority: "visual_first",
    } as never;
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(c.kind).toBe("timeline_frame");
    if (c.kind === "timeline_frame") {
      expect(c.mediaKind).toBe("image");
      expect(c.promptText).toBe("A lone figure on a ridge");
    }
  });

  it("returns idle when playhead is in a gap (no intersecting clip)", () => {
    const timeline = {
      media_mode: "image",
      duration_sec: 5,
      image_clips: [
        { id: "ic1", asset_id: "ast1", start: 0, length: 2, label: "Shot A", role: "guide" },
      ],
      video_clips: [],
      prompt_segments: [],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 4,
      guidance_priority: "visual_first",
    } as never;
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 4,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(c.kind).toBe("idle");
  });

  it("failed job preserves the latest streamed draft frame", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      master: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "failed" }),
      preview: { sourceUrl: "/preview_draft.png", sequenceNumber: 7 },
    });
    expect(c.kind).toBe("failed");
    if (c.kind === "failed") expect(c.previewSrc).toBe("/preview_draft.png");
  });

  it("cancelled job preserves the latest streamed draft frame", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      master: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "cancelled" }),
      preview: { sourceUrl: "/preview_draft.png", sequenceNumber: 3 },
    });
    expect(c.kind).toBe("cancelled");
    if (c.kind === "cancelled") expect(c.previewSrc).toBe("/preview_draft.png");
  });

  it("failed job without a streamed draft falls back cleanly (previewSrc null)", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      master: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "failed" }),
      preview: null,
    });
    expect(c.kind).toBe("failed");
    if (c.kind === "failed") expect(c.previewSrc).toBeNull();
  });

  it("creator-dismissed failure no longer pins the monitor (falls through)", () => {
    const job = makeJob({ status: "failed" });
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      master: { dismissedFailureJobIds: [job.id] } as never,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: job,
      preview: null,
    });
    expect(c.kind).not.toBe("failed");
  });

  it("a NEW failure (different job id) still shows the failed overlay", () => {
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      master: { dismissedFailureJobIds: ["some-older-job-id"] } as never,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "failed" }),
      preview: null,
    });
    expect(c.kind).toBe("failed");
  });

  it("dismissal never suppresses the cancelled overlay", () => {
    const job = makeJob({ status: "cancelled" });
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline: null,
      master: { dismissedFailureJobIds: [job.id] } as never,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: job,
      preview: null,
    });
    expect(c.kind).toBe("cancelled");
  });
});

// Reference baseProject to satisfy linters in shared fixtures.
void baseProject;
