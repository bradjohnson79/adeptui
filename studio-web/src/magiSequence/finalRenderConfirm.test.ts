import { describe, expect, it } from "vitest";
import { createEmptySequence, type MagiClip } from "./engine";
import {
  applyFinalRenderJob,
  buildFinalRenderConfirm,
  emptyFinalRenderSession,
  humanJobError,
  mergeStageLog,
  monitorPreviewAssetId,
  pictureClipsForRender,
  progressPercent,
} from "./finalRenderConfirm";

function clip(partial: Partial<MagiClip> & Pick<MagiClip, "id" | "startFrame" | "durationFrames">): MagiClip {
  return {
    trackId: "trk_v",
    assetId: `${partial.id}-asset`,
    name: partial.id,
    inPoint: 0,
    outPoint: partial.durationFrames,
    ...partial,
  };
}

describe("MAGI final render confirmation", () => {
  it("reads the first picture clip grade and leaves upscale off unless finishing says it is on", () => {
    const doc = createEmptySequence("proj", 24);
    doc.durationFrames = 240;
    doc.tracks = [
      { id: "trk_v", kind: "video", label: "Video", order: 0 },
      { id: "trk_a", kind: "audio", label: "Audio", order: 1 },
      { id: "trk_m", kind: "music", label: "Music", order: 2, muted: true },
      { id: "trk_s", kind: "sfx", label: "SFX", order: 3 },
    ];
    doc.clips = [
      clip({ id: "first", name: "Opening", startFrame: 0, durationFrames: 120 }),
      clip({ id: "second", name: "Later", startFrame: 120, durationFrames: 120, trackId: "trk_v" }),
      clip({ id: "song", name: "Theme", startFrame: 0, durationFrames: 120, trackId: "trk_m", assetId: "music-1" }),
    ];
    doc.finishing = {
      clipGrades: {
        second: { presetId: "noir", lightingPresetId: "cool", params: { contrast: 0.2 } },
        first: { presetId: "golden_hour", lightingPresetId: "warm", params: { brightness: 0.1, contrast: 0 } },
      },
      audio: { range: "entire", musicAssetId: "music-1", sfxAssetId: "sfx-1" },
      upscale: { enabled: false, engine: "ffmpeg-scale", model: "lanczos", target: "1440p" },
    };
    expect(pictureClipsForRender(doc).map((item) => item.id)).toEqual(["first", "second"]);
    const built = buildFinalRenderConfirm({
      sequence: doc,
      range: "entire",
      selectedClipId: "second",
      upscaleEnabled: false,
      upscaleEngine: "ffmpeg-scale",
      upscaleModel: "lanczos",
      upscaleTarget: "1440p",
      resolvedUpscale: { id: "1440p", width: 2560, height: 1440, aspect: "16:9" },
      assets: [{ id: "music-1", filename: "theme.wav" }, { id: "sfx-1", tag: "Rain" }],
    });
    expect(built.request.outputName).toBe("");
    expect(built.request.upscale).toEqual({ enabled: false });
    expect(built.request.includeAudio).toBe(true);
    expect(JSON.stringify(built.request.upscale)).not.toContain("engine");
    const video = built.sections.find((section) => section.id === "video");
    expect(video?.rows.find((row) => row.label === "Color grade")?.value).toBe("Golden Hour on Opening");
    expect(video?.rows.find((row) => row.label === "Lighting")?.value).toBe("Warm");
    expect(video?.rows.find((row) => row.label === "Adjustments")?.value).toBe("Exposure");
    const upscale = built.sections.find((section) => section.id === "upscale");
    expect(upscale?.rows.find((row) => row.label === "Video upscale")?.value).toBe("Off");
    expect(upscale?.rows.find((row) => row.label === "Method")).toBeUndefined();
    const audio = built.sections.find((section) => section.id === "audio");
    expect(audio?.rows.map((row) => [row.label, row.value])).toEqual([
      ["Audio", "Included"],
      ["Range", "Entire edit"],
      ["Source audio", "On"],
      ["Music", "Muted"],
      ["Sound effects", "Included · Rain"],
    ]);
    expect(built.sections.map((section) => section.title)).toEqual(["Video", "Upscale", "Audio", "Output"]);
  });

  it("sends the current upscale method only when finishing upscale is on", () => {
    const doc = createEmptySequence("proj", 24);
    doc.tracks = [{ id: "trk_v", kind: "video", label: "Video", order: 0 }];
    doc.clips = [clip({ id: "shot", name: "Shot", startFrame: 0, durationFrames: 48 })];
    doc.finishing = { audio: { range: "clip" }, upscale: { enabled: true, engine: "ffmpeg-scale", model: "lanczos", target: "1080p" } };
    const built = buildFinalRenderConfirm({
      sequence: doc,
      range: "clip",
      selectedClipId: "shot",
      upscaleEnabled: true,
      upscaleEngine: "ffmpeg-scale",
      upscaleModel: "lanczos",
      upscaleTarget: "1080p",
      resolvedUpscale: { id: "1080p", width: 1920, height: 1080, aspect: "16:9" },
      assets: [],
    });
    expect(built.request.upscale).toEqual({
      enabled: true,
      engine: "ffmpeg-scale",
      model: "lanczos",
      target: "1080p",
    });
    expect(built.request.range).toBe("clip");
    expect(built.request.clipId).toBe("shot");
    const upscale = built.sections.find((section) => section.id === "upscale");
    expect(upscale?.rows.find((row) => row.label === "Video upscale")?.value).toBe("On");
    expect(upscale?.rows.find((row) => row.label === "Method")?.value).toBe("FFmpeg (fast)");
    expect(upscale?.rows.find((row) => row.label === "Output size")?.value).toContain("1920×1080");
    expect(built.sections.find((section) => section.id === "output")?.rows.find((row) => row.label === "Duration")?.value).toBe("00:00:02:00");
  });

  it("keeps job progress and stage notes without inventing 100 percent early", () => {
    expect(progressPercent(1, "running")).toBe(99);
    expect(progressPercent(0.18, "running")).toBe(18);
    expect(progressPercent(1, "done")).toBe(100);
    const session = emptyFinalRenderSession();
    const running = applyFinalRenderJob(session, {
      status: "running",
      stage: "Rendering final frames",
      message: "Rendering final frames…",
      progress: 0.18,
      history: JSON.stringify({
        stages: [
          { stage: "Preparing scene", message: "Validating current MAGI settings…", progress: 0.08 },
          { stage: "Rendering final frames", message: "Rendering final frames…", progress: 0.18 },
        ],
      }),
    });
    expect(running.phase).toBe("running");
    expect(running.log.map((note) => note.message)).toEqual([
      "Validating current MAGI settings…",
      "Rendering final frames…",
    ]);
    const again = applyFinalRenderJob(running, {
      status: "running",
      stage: "Rendering final frames",
      message: "Rendering final frames…",
      progress: 0.18,
      history: JSON.stringify({
        stages: [
          { stage: "Preparing scene", message: "Validating current MAGI settings…", progress: 0.08 },
          { stage: "Rendering final frames", message: "Rendering final frames…", progress: 0.18 },
        ],
      }),
    });
    expect(again.log).toHaveLength(2);
    const done = applyFinalRenderJob({ ...again, jobId: "job-9" }, {
      status: "done",
      jobId: "job-9",
      stage: "Completed",
      message: "Final render ready",
      progress: 1,
      history: JSON.stringify({ assetId: "asset-9", stages: [] }),
    });
    expect(done.phase).toBe("done");
    expect(done.assetId).toBe("asset-9");
    expect(done.jobId).toBe("job-9");
    expect(monitorPreviewAssetId("asset-9", "source-clip", "source-clip")).toBe("asset-9");
    expect(monitorPreviewAssetId(null, "source-clip", "asset-9")).toBe("source-clip");
    expect(monitorPreviewAssetId(null, null, "asset-9")).toBe("asset-9");
    expect(done.log[done.log.length - 1]?.message).toBe("Complete");
    const failed = applyFinalRenderJob(emptyFinalRenderSession(), {
      status: "failed",
      stage: "Failed",
      message: 'Traceback (most recent call last):\nFile "render.py", line 1\nRuntimeError: Disk is full',
      progress: 0.18,
    });
    expect(failed.phase).toBe("failed");
    expect(failed.error).toBe("Disk is full");
    expect(failed.log.some((note) => note.failed)).toBe(true);
    expect(mergeStageLog([{ stage: "A", message: "A" }], [{ stage: "A", message: "A" }])).toHaveLength(1);
    expect(humanJobError("")).toBe("Final render stopped before it finished.");
  });
});
