import { describe, expect, it } from "vitest";
import type { DirectorTimeline } from "../DirectorTracks";
import { collectTimelineAudioAtTime } from "./collectTimelineAudioAtTime";

function timeline(): DirectorTimeline {
  return {
    media_mode: "image",
    duration_sec: 8,
    image_clips: [],
    video_clips: [],
    prompt_segments: [],
    audio_clips: [],
    sfx_clips: [
      { id: "k1", asset_id: "sfx-metal", start: 0, length: 0.45, label: "Korri footsteps", volume: 0.32 },
      { id: "a1", asset_id: "sfx-metal", start: 0.22, length: 0.45, label: "Anadriya footsteps", volume: 0.32 },
    ],
    lipsync: {
      tracks: [
        {
          id: "lt-k",
          slot: 1,
          label: "Korri Voice",
          enabled: true,
          clips: [{ id: "kd", start: 0.4, length: 3.28, label: "Korri Voice", audio_asset_id: "dlg-k" }],
        },
        {
          id: "lt-a",
          slot: 2,
          label: "Anadriya Voice",
          enabled: true,
          clips: [{ id: "ad", start: 3.85, length: 2.72, label: "Anadriya Voice", audio_asset_id: "dlg-a" }],
        },
      ],
    },
    playhead: 0,
  };
}

describe("collectTimelineAudioAtTime", () => {
  it("keeps independently timed footsteps audible together", () => {
    const layers = collectTimelineAudioAtTime(timeline(), null, 0.3);
    const labels = layers.map((layer) => layer.label).sort();
    expect(labels).toEqual(["Anadriya footsteps", "Korri footsteps"]);
    expect(layers.every((layer) => layer.kind === "sfx")).toBe(true);
  });

  it("plays Korri dialogue without overlapping Anadriya", () => {
    const atKorri = collectTimelineAudioAtTime(timeline(), null, 1.2);
    expect(atKorri.some((layer) => layer.kind === "dialogue" && layer.assetId === "dlg-k")).toBe(true);
    expect(atKorri.some((layer) => layer.assetId === "dlg-a")).toBe(false);
    const atAna = collectTimelineAudioAtTime(timeline(), null, 4.2);
    expect(atAna.some((layer) => layer.kind === "dialogue" && layer.assetId === "dlg-a")).toBe(true);
    expect(atAna.some((layer) => layer.assetId === "dlg-k")).toBe(false);
  });

  it("mutes a legacy sfx clip to zero while preserving stored volume", () => {
    const tl = timeline();
    tl.sfx_clips[0] = { ...tl.sfx_clips[0], volume: 0.5, muted: true };
    const layers = collectTimelineAudioAtTime(tl, null, 0.3);
    const korri = layers.find((l) => l.label === "Korri footsteps");
    expect(korri).toBeDefined();
    expect(korri!.volume).toBe(0);
  });

  it("keeps unmuted legacy sfx volume clamped to the fallback", () => {
    const tl = timeline();
    tl.sfx_clips[0] = { ...tl.sfx_clips[0], volume: 2, muted: false };
    const layers = collectTimelineAudioAtTime(tl, null, 0.3);
    const korri = layers.find((l) => l.label === "Korri footsteps");
    expect(korri).toBeDefined();
    expect(korri!.volume).toBe(1);
  });

  it("mutes batch audio clips to zero", () => {
    const master = {
      batchBlocks: [
        {
          id: "bb1",
          sceneId: "s1",
          order: 0,
          label: "Batch 1",
          status: "Approved",
          generatorOverride: false,
          duration: { plannedDuration: 5 },
          sourceAnchors: [],
          promptSegments: [],
          visualClips: [],
          audioClips: [{ id: "ba1", kind: "audio", assetId: "batch-music", start: 0, length: 5, label: "Score", volume: 0.8, muted: true, trimStart: 0, fade_in: 0, fade_out: 0 }],
          sfxClips: [],
          cameraInstructions: [],
        } as never,
      ],
    };
    const layers = collectTimelineAudioAtTime(null, master, 1);
    expect(layers[0].volume).toBe(0);
  });

  it("keeps batch sfx volume when unmuted", () => {
    const master = {
      batchBlocks: [
        {
          id: "bb1",
          sceneId: "s1",
          order: 0,
          label: "Batch 1",
          status: "Approved",
          generatorOverride: false,
          duration: { plannedDuration: 5 },
          sourceAnchors: [],
          promptSegments: [],
          visualClips: [],
          audioClips: [],
          sfxClips: [{ id: "bs1", kind: "sfx", assetId: "batch-sfx", start: 0, length: 5, label: "Bang", volume: 0.4, muted: false, trimStart: 0, fade_in: 0, fade_out: 0 }],
          cameraInstructions: [],
        } as never,
      ],
    };
    const layers = collectTimelineAudioAtTime(null, master, 1);
    expect(layers[0].volume).toBe(0.4);
  });

  it("plays batch-2 music at scene offset without director fallback ghost", () => {
    const master = {
      batchBlocks: [
        {
          id: "bb1",
          sceneId: "s1",
          order: 0,
          label: "Batch 1",
          status: "Approved",
          generatorOverride: false,
          duration: { plannedDuration: 10 },
          sourceAnchors: [],
          promptSegments: [],
          visualClips: [],
          audioClips: [{ id: "ba1", kind: "audio", assetId: "music-b1", start: 0, length: 10, label: "B1", volume: 0.9, muted: false, trimStart: 0, fade_in: 0, fade_out: 0 }],
          sfxClips: [{ id: "bs1", kind: "sfx", assetId: "sfx-b1", start: 0, length: 10, label: "S1", volume: 0.5, muted: false, trimStart: 0, fade_in: 0, fade_out: 0 }],
          cameraInstructions: [],
        } as never,
        {
          id: "bb2",
          sceneId: "s1",
          order: 1,
          label: "Batch 2",
          status: "Approved",
          generatorOverride: false,
          duration: { plannedDuration: 10 },
          sourceAnchors: [],
          promptSegments: [],
          visualClips: [],
          audioClips: [{ id: "ba2", kind: "audio", assetId: "music-b2", start: 0, length: 10, label: "B2", volume: 0.9, muted: false, trimStart: 0, fade_in: 0, fade_out: 0 }],
          sfxClips: [{ id: "bs2", kind: "sfx", assetId: "sfx-b2", start: 0, length: 10, label: "S2", volume: 0.5, muted: false, trimStart: 0, fade_in: 0, fade_out: 0 }],
          cameraInstructions: [],
        } as never,
      ],
    };
    const staleDirector = {
      media_mode: "video" as const,
      duration_sec: 20,
      image_clips: [],
      video_clips: [],
      prompt_segments: [],
      audio_clips: [{ id: "legacy", asset_id: "ghost", start: 0, length: 20, label: "ghost" }],
      sfx_clips: [],
      playhead: 0,
    };
    const atBatch2 = collectTimelineAudioAtTime(staleDirector, master, 15);
    expect(atBatch2.some((l) => l.assetId === "music-b2")).toBe(true);
    expect(atBatch2.some((l) => l.assetId === "sfx-b2")).toBe(true);
    expect(atBatch2.some((l) => l.assetId === "ghost")).toBe(false);
    expect(atBatch2.some((l) => l.assetId === "music-b1")).toBe(false);
  });

  it("stays silent in a later batch when that batch owns no Music clips", () => {
    const master = {
      batchBlocks: [
        {
          id: "bb1",
          sceneId: "s1",
          order: 0,
          label: "Batch 1",
          status: "Approved",
          generatorOverride: false,
          duration: { plannedDuration: 10 },
          sourceAnchors: [],
          promptSegments: [],
          visualClips: [],
          audioClips: [{ id: "ba1", kind: "audio", assetId: "music-b1", start: 0, length: 10, label: "B1", volume: 1, muted: false, trimStart: 0, fade_in: 0, fade_out: 0 }],
          sfxClips: [],
          cameraInstructions: [],
        } as never,
        {
          id: "bb2",
          sceneId: "s1",
          order: 1,
          label: "Batch 2",
          status: "Approved",
          generatorOverride: false,
          duration: { plannedDuration: 10 },
          sourceAnchors: [],
          promptSegments: [],
          visualClips: [],
          audioClips: [],
          sfxClips: [],
          cameraInstructions: [],
        } as never,
      ],
    };
    const staleDirector = {
      media_mode: "video" as const,
      duration_sec: 20,
      image_clips: [],
      video_clips: [],
      prompt_segments: [],
      audio_clips: [{ id: "legacy", asset_id: "ghost", start: 0, length: 20, label: "ghost" }],
      sfx_clips: [],
      playhead: 0,
    };
    const layers = collectTimelineAudioAtTime(staleDirector, master, 15);
    expect(layers.filter((l) => l.kind === "audio")).toEqual([]);
  });

});
