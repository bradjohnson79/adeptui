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

  it("does not use the 1 Frame start still as the Timeline generation picture", () => {
    const c = resolvePreviewComposition({
      scene: { ...baseScene, start_asset_id: "one-frame-still" },
      timeline: null,
      selection: nullSelection,
      playheadSec: 0,
      libraryAsset: null,
      activeJob: makeJob({ status: "running", stage: "sampling" }),
      preview: null,
      master: null,
    });
    expect(c.kind).toBe("generation_draft");
    if (c.kind === "generation_draft") {
      expect(c.previewSrc).toBe("");
      expect(c.sourceStill).toBe("");
      expect(c.sourceStill).not.toContain("one-frame-still");
    }
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

  it("playhead video clip wins over leftover scene output_path", () => {
    const timeline = {
      media_mode: "video",
      duration_sec: 10,
      image_clips: [],
      video_clips: [
        { id: "bbclip_b1", asset_id: "asset-b1", start: 0, length: 5, label: "Batch 1" },
        { id: "bbclip_b2", asset_id: "asset-b2", start: 5, length: 5, label: "Batch 2" },
      ],
      prompt_segments: [],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 1,
      guidance_priority: "visual_first",
    } as never;
    const atB1 = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "projects/x/renders/scene_0_latest.mp4" },
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(atB1.kind).toBe("timeline_frame");
    if (atB1.kind === "timeline_frame") expect(atB1.mediaKind).toBe("video");
    const atB2 = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "projects/x/renders/scene_0_latest.mp4" },
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 6,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(atB2.kind).toBe("timeline_frame");
    if (atB2.kind === "timeline_frame") expect(atB2.mediaKind).toBe("video");
  });

  it("playhead Batch Visual wins over lipsync_output_path (atomic multi-batch A/V)", () => {
    const timeline = {
      media_mode: "video",
      duration_sec: 20,
      image_clips: [],
      video_clips: [
        { id: "bbclip_b1", asset_id: "asset-b1", start: 0, length: 10, label: "Batch 1" },
        { id: "bbclip_b2", asset_id: "asset-b2", start: 10, length: 10, label: "Batch 2" },
      ],
      prompt_segments: [],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 1,
      guidance_priority: "visual_first",
    } as never;
    const scene = {
      ...baseScene,
      output_path: "projects/x/renders/scene_0_master.mp4",
      lipsync_output_path: "projects/x/renders/scene_0_retake.mp4",
    };
    const atB1 = resolvePreviewComposition({
      scene,
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(atB1.kind).toBe("timeline_frame");
    if (atB1.kind === "timeline_frame") {
      expect(atB1.mediaKind).toBe("video");
      expect(atB1.videoAssetId).toBe("asset-b1");
      expect(atB1.sourceClipId).toBe("bbclip_b1");
      expect(atB1.visualLocalTime).toBeCloseTo(1, 5);
    }
    const atB2 = resolvePreviewComposition({
      scene,
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 12,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(atB2.kind).toBe("timeline_frame");
    if (atB2.kind === "timeline_frame") {
      expect(atB2.mediaKind).toBe("video");
      expect(atB2.videoAssetId).toBe("asset-b2");
      expect(atB2.sourceClipId).toBe("bbclip_b2");
      expect(atB2.visualLocalTime).toBeCloseTo(2, 5);
    }
  });

  it("lipsync_output_path is NOT Preview authority when no intersecting video clip (use output_path)", () => {
    const c = resolvePreviewComposition({
      scene: {
        ...baseScene,
        output_path: "projects/x/renders/scene_0_master.mp4",
        lipsync_output_path: "projects/x/renders/scene_0_retake.mp4",
      },
      timeline: {
        media_mode: "video",
        duration_sec: 10,
        image_clips: [],
        video_clips: [],
        prompt_segments: [],
        camera_clips: [],
        audio_clips: [],
        sfx_clips: [],
        lipsync: { tracks: [] },
        playhead: 1,
        guidance_priority: "visual_first",
      } as never,
      master: null,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(c.kind).toBe("final_output");
    if (c.kind === "final_output") {
      expect(c.mediaKind).toBe("video");
      expect(c.src).toContain("scene_0_master.mp4");
      expect(c.src).not.toContain("scene_0_retake.mp4");
    }
  });

  it("approved Batch take wins over lipsync_output_path even when a scene stitch exists", () => {
    const master = {
      batchBlocks: [
        { id: "bb1", order: 0, status: "Approved", duration: { plannedDuration: 10 }, visualClips: [], approvedClip: { assetId: "approved-b1", playable: true } },
      ],
      sceneStitch: {
        assetId: "stitch-10",
        sourceBatchIds: ["bb1"],
        sourceAssetIds: ["approved-b1"],
      },
    } as never;
    const c = resolvePreviewComposition({
      scene: {
        ...baseScene,
        output_path: "projects/x/renders/scene_0_master.mp4",
        lipsync_output_path: "projects/x/renders/scene_0_retake.mp4",
      },
      timeline: { media_mode: "video", duration_sec: 10, image_clips: [], video_clips: [{ id: "bbclip_bb1", asset_id: "approved-b1", start: 0, length: 10, label: "Batch 1" }], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 1, guidance_priority: "visual_first" } as never,
      master,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(c.kind).toBe("timeline_frame");
    if (c.kind === "timeline_frame") {
      expect(c.videoAssetId).toBe("approved-b1");
      expect(c.mediaKind).toBe("video");
    }
  });

  it("parked stitch / output_path win over lipsync_output_path when no batch visual", () => {
    const master = {
      batchBlocks: [
        { id: "bb1", order: 0, status: "Ready", duration: { plannedDuration: 10 }, visualClips: [] },
      ],
      sceneStitch: {
        assetId: "stitch-10",
        sourceBatchIds: ["bb1"],
        sourceAssetIds: ["approved-b1"],
      },
    } as never;
    const c = resolvePreviewComposition({
      scene: {
        ...baseScene,
        output_path: "projects/x/renders/scene_0_master.mp4",
        lipsync_output_path: "projects/x/renders/scene_0_retake.mp4",
      },
      timeline: { media_mode: "video", duration_sec: 10, image_clips: [], video_clips: [], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 1, guidance_priority: "visual_first" } as never,
      master,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: null,
      preview: null,
      timelinePlaying: true,
    });
    // lipsync_output_path must not win — stitch Visual or output_path only.
    expect(["timeline_frame", "final_output"]).toContain(c.kind);
    if (c.kind === "final_output") {
      expect(c.src).toContain("scene_0_master.mp4");
      expect(c.src).not.toContain("scene_0_retake.mp4");
    }
    if (c.kind === "timeline_frame") {
      // api.assetUrl may be empty without bound project; assert not lipsync fallthrough.
      expect(JSON.stringify(c)).not.toContain("scene_0_retake");
      expect(JSON.stringify(c)).not.toContain("lipsync");
    }
  });

  it("rtclip_* Re-Take Visual wins over lipsync_output_path (A|Retake|B authority)", () => {
    const timeline = {
      media_mode: "video",
      duration_sec: 10,
      image_clips: [],
      video_clips: [
        { id: "bbclip_b1_a", asset_id: "asset-a", start: 0, length: 2, trim_start: 0, label: "A" },
        { id: "rtclip_repair1", asset_id: "asset-retake", start: 2, length: 3, trim_start: 0, label: "Retake" },
        { id: "bbclip_b1_b", asset_id: "asset-a", start: 5, length: 5, trim_start: 5, label: "B" },
      ],
      prompt_segments: [],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 3,
      guidance_priority: "visual_first",
    } as never;
    const scene = {
      ...baseScene,
      output_path: "projects/x/renders/scene_0_master.mp4",
      lipsync_output_path: "projects/x/renders/scene_0_lipsync.mp4",
    };
    const c = resolvePreviewComposition({
      scene,
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 3.5,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    expect(c.kind).toBe("timeline_frame");
    if (c.kind === "timeline_frame") {
      expect(c.sourceClipId).toBe("rtclip_repair1");
      expect(c.videoAssetId).toBe("asset-retake");
      expect(c.visualSrc).not.toContain("lipsync");
    }
  });

  it("library inspect and active generation still win over a media retake", () => {
    const scene = {
      ...baseScene,
      output_path: "projects/x/renders/scene_0_master.mp4",
      lipsync_output_path: "projects/x/renders/scene_0_retake.mp4",
    };
    const lib = resolvePreviewComposition({
      scene,
      timeline: null,
      master: null,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: makeAsset({ id: "lib", kind: "video" }),
      activeJob: null,
      preview: null,
    });
    expect(lib.kind).toBe("library");
    const draft = resolvePreviewComposition({
      scene,
      timeline: null,
      master: null,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: makeJob({ status: "running" }),
      preview: { sourceUrl: "/preview.mp4" },
    });
    expect(draft.kind).toBe("generation_draft");
  });

  it("media_mode video with empty video_clips does not claim the approved take as placed", () => {
    const master = {
      batchBlocks: [
        {
          id: "bb1",
          order: 0,
          label: "Batch 1",
          duration: { plannedDuration: 5 },
          visualClips: [],
          approvedClip: { assetId: "approved-b1", playable: true },
        },
        {
          id: "bb2",
          order: 1,
          label: "Batch 2",
          duration: { plannedDuration: 5 },
          visualClips: [],
          approvedClip: { assetId: "approved-b2", playable: true },
        },
      ],
    } as never;
    const atB1 = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "projects/x/renders/scene_0_latest.mp4" },
      timeline: { media_mode: "video", duration_sec: 10, image_clips: [], video_clips: [], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 0, guidance_priority: "visual_first" } as never,
      master,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    if (atB1.kind === "timeline_frame") {
      expect(atB1.videoAssetId).not.toBe("approved-b1");
      expect(atB1.sourceClipId).not.toBe("bb1-approved");
    }
    const atB2 = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "projects/x/renders/scene_0_latest.mp4" },
      timeline: { media_mode: "video", duration_sec: 10, image_clips: [], video_clips: [], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 6, guidance_priority: "visual_first" } as never,
      master,
      selection: nullSelection,
      playheadSec: 6,
      libraryAsset: null,
      activeJob: null,
      preview: null,
    });
    if (atB2.kind === "timeline_frame") {
      expect(atB2.videoAssetId).not.toBe("approved-b2");
      expect(atB2.sourceClipId).not.toBe("bb2-approved");
    }
  });

  it("playhead video clip wins over leftover output_path even when newest job is done", () => {
    const timeline = {
      media_mode: "video",
      duration_sec: 10,
      image_clips: [],
      video_clips: [
        { id: "bbclip_b1", asset_id: "asset-b1", start: 0, length: 5, label: "Batch 1" },
        { id: "bbclip_b2", asset_id: "asset-b2", start: 5, length: 5, label: "Batch 2" },
      ],
      prompt_segments: [],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 1,
      guidance_priority: "visual_first",
    } as never;
    const atB1 = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "projects/x/renders/scene_0_b2_only.mp4" },
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 1,
      libraryAsset: null,
      activeJob: makeJob({ status: "done" }),
      preview: null,
    });
    expect(atB1.kind).toBe("timeline_frame");
    if (atB1.kind === "timeline_frame") expect(atB1.mediaKind).toBe("video");
    const atB2 = resolvePreviewComposition({
      scene: { ...baseScene, output_path: "projects/x/renders/scene_0_b2_only.mp4" },
      timeline,
      master: null,
      selection: nullSelection,
      playheadSec: 6,
      libraryAsset: null,
      activeJob: makeJob({ status: "done" }),
      preview: null,
    });
    expect(atB2.kind).toBe("timeline_frame");
    if (atB2.kind === "timeline_frame") expect(atB2.mediaKind).toBe("video");
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
    // SINGLE-STORE: prompt text authority is Master batch.promptSegments; the
    // legacy view prompt_segments array is retired (resolveTimelineAtTime).
    const timeline = {
      media_mode: "image",
      duration_sec: 5,
      image_clips: [
        { id: "ic1", asset_id: "ast1", start: 0, length: 3, label: "Shot A", role: "guide" },
      ],
      video_clips: [],
      prompt_segments: [],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 1,
      guidance_priority: "visual_first",
    } as never;
    const master = {
      batchBlocks: [
        {
          id: "b1",
          order: 0,
          duration: { plannedDuration: 5 },
          promptSegments: [
            { id: "ps1", start: 0, length: 3, text: "A lone figure on a ridge" },
          ],
        },
      ],
    } as never;
    const c = resolvePreviewComposition({
      scene: baseScene,
      timeline,
      master,
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

  it("play uses the stitched scene clip even when a library file is selected", () => {
    const master = {
      batchBlocks: [
        { id: "bb1", order: 0, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b1", playable: true } },
        { id: "bb2", order: 1, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b2", playable: true } },
      ],
      sceneStitch: {
        assetId: "stitch-10",
        sourceBatchIds: ["bb1", "bb2"],
        sourceAssetIds: ["approved-b1", "approved-b2"],
      },
    } as never;
    const playing = resolvePreviewComposition({
      scene: baseScene,
      timeline: { media_mode: "video", duration_sec: 10, image_clips: [], video_clips: [], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 6, guidance_priority: "visual_first" } as never,
      master,
      selection: { kind: "batch", id: "bb2" },
      playheadSec: 6,
      libraryAsset: makeAsset({ id: "lib-other", kind: "video" }),
      activeJob: null,
      preview: null,
      timelinePlaying: true,
    });
    expect(playing.kind).toBe("timeline_frame");
    if (playing.kind === "timeline_frame") {
      expect(playing.batchId).toBeNull();
      expect(playing.visualLocalTime).toBe(6);
      expect(playing.promptLabel).toBe("Full scene");
    }
  });

  it("play uses the stitched scene clip as one source", () => {
    const master = {
      batchBlocks: [
        { id: "bb1", order: 0, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b1", playable: true } },
        { id: "bb2", order: 1, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b2", playable: true } },
        { id: "bb3", order: 2, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b3", playable: true } },
      ],
      sceneStitch: {
        assetId: "stitch-15",
        sourceBatchIds: ["bb1", "bb2", "bb3"],
        sourceAssetIds: ["approved-b1", "approved-b2", "approved-b3"],
      },
    } as never;
    const timeline = {
      media_mode: "video",
      duration_sec: 15,
      image_clips: [],
      video_clips: [],
      prompt_segments: [],
      camera_clips: [],
      audio_clips: [],
      sfx_clips: [],
      lipsync: { tracks: [] },
      playhead: 6,
      guidance_priority: "visual_first",
    } as never;
    const playing = resolvePreviewComposition({
      scene: baseScene,
      timeline,
      master,
      selection: nullSelection,
      playheadSec: 6,
      libraryAsset: null,
      activeJob: null,
      preview: null,
      timelinePlaying: true,
    });
    expect(playing.kind).toBe("timeline_frame");
    if (playing.kind === "timeline_frame") {
      expect(playing.batchId).toBeNull();
      expect(playing.visualLocalTime).toBe(6);
      expect(playing.promptLabel).toBe("Full scene");
    }
  });

  it("paused batch inspection still shows that batch take after stitch", () => {
    const master = {
      batchBlocks: [
        { id: "bb1", order: 0, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b1", playable: true } },
        { id: "bb2", order: 1, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b2", playable: true } },
      ],
      sceneStitch: {
        assetId: "stitch-10",
        sourceBatchIds: ["bb1", "bb2"],
        sourceAssetIds: ["approved-b1", "approved-b2"],
      },
    } as never;
    const paused = resolvePreviewComposition({
      scene: baseScene,
      timeline: { media_mode: "video", duration_sec: 10, image_clips: [], video_clips: [
        { id: "bbclip_bb1", asset_id: "approved-b1", start: 0, length: 5, label: "Batch 1" },
        { id: "bbclip_bb2", asset_id: "approved-b2", start: 5, length: 5, label: "Batch 2" },
      ], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 6, guidance_priority: "visual_first" } as never,
      master,
      selection: { kind: "batch", id: "bb2" },
      playheadSec: 6,
      libraryAsset: null,
      activeJob: null,
      preview: null,
      timelinePlaying: false,
    });
    expect(paused.kind).toBe("timeline_frame");
    if (paused.kind === "timeline_frame") {
      expect(paused.batchId).toBe("bb2");
      expect(paused.visualLocalTime).toBeLessThan(5);
      expect(paused.promptLabel).not.toBe("Full scene");
    }
  });

  it("play prefers batch Visual + stem mix over stitch when Music/SFX exist", () => {
    const master = {
      batchBlocks: [
        {
          id: "bb1",
          order: 0,
          status: "Approved",
          duration: { plannedDuration: 5 },
          visualClips: [],
          approvedClip: { assetId: "approved-b1", playable: true },
          audioClips: [{ id: "music1", assetId: "music-uuid", start: 0, length: 5, volume: 0.33, muted: false }],
          sfxClips: [{ id: "sfx1", assetId: "sfx-uuid", start: 1, length: 1, volume: 0.5, muted: false }],
        },
        {
          id: "bb2",
          order: 1,
          status: "Approved",
          duration: { plannedDuration: 5 },
          visualClips: [],
          approvedClip: { assetId: "approved-b2", playable: true },
          audioClips: [{ id: "music2", assetId: "music-uuid-2", start: 0, length: 5, volume: 0.33, muted: false }],
        },
      ],
      sceneStitch: {
        assetId: "stitch-10",
        sourceBatchIds: ["bb1", "bb2"],
        sourceAssetIds: ["approved-b1", "approved-b2"],
      },
    } as never;
    const playing = resolvePreviewComposition({
      scene: baseScene,
      timeline: { media_mode: "video", duration_sec: 10, image_clips: [], video_clips: [
        { id: "bbclip_bb1", asset_id: "approved-b1", start: 0, length: 5, label: "Batch 1" },
        { id: "bbclip_bb2", asset_id: "approved-b2", start: 5, length: 5, label: "Batch 2" },
      ], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 6, guidance_priority: "visual_first" } as never,
      master,
      selection: { kind: null },
      playheadSec: 6,
      libraryAsset: null,
      activeJob: null,
      preview: null,
      timelinePlaying: true,
    });
    expect(playing.kind).toBe("timeline_frame");
    if (playing.kind === "timeline_frame") {
      expect(playing.promptLabel).not.toBe("Full scene");
      expect(playing.batchId).toBe("bb2");
      expect(playing.videoAssetId).toBe("approved-b2");
    }
  });

  it("unstitched suffix batch falls through while playing", () => {
    const master = {
      batchBlocks: [
        { id: "bb1", order: 0, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b1", playable: true } },
        { id: "bb2", order: 1, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b2", playable: true } },
        { id: "bb3", order: 2, status: "Approved", duration: { plannedDuration: 5 }, visualClips: [], approvedClip: { assetId: "approved-b3", playable: true } },
      ],
      sceneStitch: {
        assetId: "stitch-10",
        sourceBatchIds: ["bb1", "bb2"],
        sourceAssetIds: ["approved-b1", "approved-b2"],
      },
    } as never;
    const suffix = resolvePreviewComposition({
      scene: baseScene,
      timeline: { media_mode: "video", duration_sec: 15, image_clips: [], video_clips: [
        { id: "bbclip_bb1", asset_id: "approved-b1", start: 0, length: 5, label: "Batch 1" },
        { id: "bbclip_bb2", asset_id: "approved-b2", start: 5, length: 5, label: "Batch 2" },
        { id: "bbclip_bb3", asset_id: "approved-b3", start: 10, length: 5, label: "Batch 3" },
      ], prompt_segments: [], camera_clips: [], audio_clips: [], sfx_clips: [], lipsync: { tracks: [] }, playhead: 12, guidance_priority: "visual_first" } as never,
      master,
      selection: nullSelection,
      playheadSec: 12,
      libraryAsset: null,
      activeJob: null,
      preview: null,
      timelinePlaying: true,
    });
    expect(suffix.kind).toBe("timeline_frame");
    if (suffix.kind === "timeline_frame") {
      expect(suffix.batchId).toBe("bb3");
      expect(suffix.promptLabel).not.toBe("Full scene");
    }
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
