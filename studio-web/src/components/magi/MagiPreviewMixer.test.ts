import { describe, expect, it } from "vitest";
import { createEmptySequence } from "../../magiSequence/engine";
import { audioLaneOwnsPlayback, previewStemVolume } from "./MagiPreviewMixer";

describe("audioLaneOwnsPlayback", () => {
  it("is false when only VIDEO exists", () => {
    const doc = createEmptySequence("p", 24);
    const video = doc.tracks.find((track) => track.kind === "video")!;
    doc.clips = [
      {
        id: "c1",
        trackId: video.id,
        assetId: "pub",
        startFrame: 0,
        durationFrames: 240,
        inPoint: 0,
        outPoint: 240,
      },
    ];
    expect(audioLaneOwnsPlayback(doc, 10)).toBe(false);
  });

  it("is true when AUDIO covers the playhead", () => {
    const doc = createEmptySequence("p", 24);
    const audio = doc.tracks.find((track) => track.kind === "audio")!;
    doc.clips = [
      {
        id: "a1",
        trackId: audio.id,
        assetId: "pub",
        startFrame: 0,
        durationFrames: 240,
        inPoint: 0,
        outPoint: 240,
        ingestRole: "published_master_audio",
      },
    ];
    expect(audioLaneOwnsPlayback(doc, 10)).toBe(true);
  });
});

describe("previewStemVolume", () => {
  it("keeps dialogue full and music under it", () => {
    expect(previewStemVolume("audio", 1)).toBe(1);
    expect(previewStemVolume("music", 1)).toBeCloseTo(0.28);
    expect(previewStemVolume("sfx", 1)).toBeCloseTo(0.35);
    expect(previewStemVolume("music", 0.5)).toBeCloseTo(0.14);
  });
});
