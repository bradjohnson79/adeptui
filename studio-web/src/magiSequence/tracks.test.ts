import { describe, expect, it } from "vitest";
import { createEmptySequence } from "./engine";
import { magiTrackHeaderControl, migrateToPostProductionTracks, visibleMagiTracks } from "./tracks";
import type { MagiSequenceDocument } from "./types";

function legacySequence(): MagiSequenceDocument {
  const doc = createEmptySequence("proj-legacy", 24);
  doc.tracks = [
    { id: "trk_v1", kind: "video", label: "V1", order: 0 },
    { id: "trk_v2", kind: "video", label: "V2", order: 1 },
    { id: "trk_i1", kind: "image", label: "I1", order: 2 },
    { id: "trk_a1", kind: "audio", label: "A1", order: 3 },
    { id: "trk_fx", kind: "fx", label: "FX", order: 4 },
    { id: "trk_m", kind: "mask", label: "M", order: 5 },
    { id: "trk_t1", kind: "text", label: "T1", order: 6 },
  ];
  doc.clips = [
    {
      id: "clip_v",
      trackId: "trk_v2",
      assetId: "asset_video",
      name: "Picture",
      startFrame: 0,
      durationFrames: 24,
      inPoint: 0,
      outPoint: 24,
    },
    {
      id: "clip_a",
      trackId: "trk_a1",
      assetId: "asset_audio",
      name: "Dialogue",
      startFrame: 0,
      durationFrames: 24,
      inPoint: 0,
      outPoint: 24,
    },
    {
      id: "clip_fx",
      trackId: "trk_fx",
      assetId: "asset_sfx",
      name: "Whoosh",
      startFrame: 0,
      durationFrames: 12,
      inPoint: 0,
      outPoint: 12,
    },
    {
      id: "clip_mask",
      trackId: "trk_m",
      assetId: "asset_mask",
      name: "Mask residue",
      startFrame: 0,
      durationFrames: 8,
      inPoint: 0,
      outPoint: 8,
    },
  ];
  doc.finishing = { audio: { musicAssetId: "asset_music" } };
  return doc;
}

describe("MAGI post-production tracks", () => {
  it("creates OBJECTS 1 / VIDEO / AUDIO / MUSIC / SFX on empty sequences", () => {
    const doc = createEmptySequence("proj-a", 24);
    expect(visibleMagiTracks(doc.tracks).map((track) => track.label)).toEqual([
      "OBJECTS 1",
      "VIDEO",
      "AUDIO",
      "MUSIC",
      "SFX",
    ]);
    expect(doc.tracks).toHaveLength(5);
  });

  it("migrates leftover production tracks without dropping clips", () => {
    const migrated = migrateToPostProductionTracks(legacySequence());
    const visible = visibleMagiTracks(migrated.tracks);
    expect(visible.map((track) => `${track.kind}:${track.label}`)).toEqual([
      "objects:OBJECTS 1",
      "video:VIDEO",
      "audio:AUDIO",
      "music:MUSIC",
      "sfx:SFX",
    ]);
    expect(migrated.clips).toHaveLength(4);
    expect(migrated.clips.map((clip) => clip.id).sort()).toEqual([
      "clip_a",
      "clip_fx",
      "clip_mask",
      "clip_v",
    ]);
    const video = visible.find((track) => track.kind === "video")!;
    const audio = visible.find((track) => track.kind === "audio")!;
    const sfx = visible.find((track) => track.kind === "sfx")!;
    expect(migrated.clips.find((clip) => clip.id === "clip_v")?.trackId).toBe(video.id);
    expect(migrated.clips.find((clip) => clip.id === "clip_a")?.trackId).toBe(audio.id);
    expect(migrated.clips.find((clip) => clip.id === "clip_fx")?.trackId).toBe(sfx.id);
    expect(migrated.clips.find((clip) => clip.id === "clip_mask")?.trackId).toBe("trk_m");
  });

  it("migrates GRAPHICS to OBJECTS 1 and keeps a second objects lane above it", () => {
    const doc = createEmptySequence("proj-objects", 24);
    doc.tracks = [
      { id: "trk_v", kind: "video", label: "VIDEO", order: 0 },
      { id: "trk_g", kind: "graphics", label: "GRAPHICS", order: 1 },
      { id: "trk_o2", kind: "objects", label: "OBJECTS 2", order: 2, objectsSlot: 2 },
      { id: "trk_a", kind: "audio", label: "AUDIO", order: 3 },
      { id: "trk_m", kind: "music", label: "MUSIC", order: 4 },
      { id: "trk_s", kind: "sfx", label: "SFX", order: 5 },
    ];
    const migrated = migrateToPostProductionTracks(doc);
    expect(visibleMagiTracks(migrated.tracks).map((track) => track.label)).toEqual([
      "OBJECTS 2",
      "OBJECTS 1",
      "VIDEO",
      "AUDIO",
      "MUSIC",
      "SFX",
    ]);
    expect(migrated.tracks.filter((track) => track.kind === "objects")).toHaveLength(2);
  });
});

describe("magiTrackHeaderControl", () => {
  it("gives audio stems a mute control and picture tracks an eye", () => {
    expect(magiTrackHeaderControl("audio")).toBe("mute");
    expect(magiTrackHeaderControl("music")).toBe("mute");
    expect(magiTrackHeaderControl("sfx")).toBe("mute");
    expect(magiTrackHeaderControl("video")).toBe("eye");
    expect(magiTrackHeaderControl("objects")).toBe("eye");
    expect(magiTrackHeaderControl("graphics")).toBe("eye");
    expect(magiTrackHeaderControl("fx")).toBeNull();
  });
});
