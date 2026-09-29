import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  isRetakeVisualClipId,
  lipsyncDialogueActiveAt,
  parseSceneLipsyncTracks,
  shouldMutePreviewVideoSoundtrack,
} from "./shouldMutePreviewVideoSoundtrack";

const tracks = [
  {
    enabled: true,
    audio_asset_id: "dlg-a",
    clips: [{ start: 0.1, length: 2.8, audio_asset_id: "dlg-a" }],
  },
  {
    enabled: true,
    audio_asset_id: "dlg-k",
    clips: [{ start: 2.9, length: 2.2 }],
  },
];

describe("shouldMutePreviewVideoSoundtrack (Re-Take-only / Lip Sync demotion)", () => {
  it("does NOT mute solely because lipsync_output_path is set", () => {
    expect(
      shouldMutePreviewVideoSoundtrack({
        lipsyncOutputPath: "C:/renders/scene_8_perfretake_h3.mp4",
        tracks: [],
        playheadSec: 8,
      }),
    ).toBe(false);
  });

  it("does NOT mute for intersecting legacy lipsync clips (demoted dialogue authority)", () => {
    expect(
      shouldMutePreviewVideoSoundtrack({
        lipsyncOutputPath: null,
        tracks,
        playheadSec: 1.0,
      }),
    ).toBe(false);
    expect(
      shouldMutePreviewVideoSoundtrack({
        lipsyncOutputPath: null,
        tracks,
        playheadSec: 3.2,
      }),
    ).toBe(false);
  });

  it("never mutes under rtclip_* Re-Take Visual (retake AAC owns AV)", () => {
    expect(
      shouldMutePreviewVideoSoundtrack({
        lipsyncOutputPath: "retake.mp4",
        tracks,
        playheadSec: 1,
        activeVisualClipId: "rtclip_abc123",
      }),
    ).toBe(false);
  });

  it("does not mute library file inspection", () => {
    expect(
      shouldMutePreviewVideoSoundtrack({
        lipsyncOutputPath: "retake.mp4",
        tracks,
        playheadSec: 1,
        libraryPreview: true,
      }),
    ).toBe(false);
  });

  it("isRetakeVisualClipId detects rtclip_ prefix", () => {
    expect(isRetakeVisualClipId("rtclip_x")).toBe(true);
    expect(isRetakeVisualClipId("bbclip_b1")).toBe(false);
  });

  it("lipsyncDialogueActiveAt helper still detects windows (MAGI / diagnostics)", () => {
    expect(lipsyncDialogueActiveAt(tracks, 1.0)).toBe(true);
    expect(lipsyncDialogueActiveAt(tracks, 12)).toBe(false);
  });

  it("parses lipsync_tracks_json and ignores leftover director_json", () => {
    const parsed = parseSceneLipsyncTracks({
      lipsync_tracks_json: JSON.stringify({ tracks }),
    });
    expect(parsed).toHaveLength(2);
    expect(lipsyncDialogueActiveAt(parsed, 0.5)).toBe(true);
  });
});

describe("original-voice suppression wiring (contract)", () => {
  it("composer passes muteVideoAudio and LivePreviewMonitor mutes the video", () => {
    const preview = readFileSync(join(__dirname, "../LivePreviewMonitor.tsx"), "utf8");
    const composer = readFileSync(join(__dirname, "./TimelinePreviewComposer.tsx"), "utf8");
    expect(composer).toContain("shouldMutePreviewVideoSoundtrack({");
    expect(composer).toContain("muteVideoAudio={muteVideoAudio}");
    expect(composer).toContain("activeVisualClipId");
    expect(preview).toContain("muted={suppressOriginalVoice}");
    expect(preview).toContain("v.muted = suppressOriginalVoice");
    expect(preview).toContain("data-suppress-original-voice");
    expect(composer).not.toContain("shouldSuppressPreviewVideoAudio");
    expect(preview).not.toContain("shouldSuppressPreviewVideoAudio");
  });
});
