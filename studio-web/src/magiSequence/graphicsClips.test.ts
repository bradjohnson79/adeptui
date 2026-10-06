import { describe, expect, it } from "vitest";
import { createEmptySequence } from "./engine";
import {
  GRAPHICS_CLIP_PREFIX,
  isGraphicsClipId,
  mergeGraphicsIntoSequence,
  overlayIdFromGraphicsClip,
  overlayToGraphicsClip,
  persistableSequenceClips,
} from "./graphicsClips";
import { createImageElement, createLowerThirdGroup, createTextElement } from "../components/magi/overlays/types";
import { findObjectsTrack } from "./tracks";

describe("MAGI Objects clip projection", () => {
  it("projects overlays onto Objects 1 without mutating persisted media clips", () => {
    const doc = createEmptySequence("proj-g", 24);
    const video = doc.tracks.find((track) => track.kind === "video")!;
    doc.clips = [
      {
        id: "clip_master",
        trackId: video.id,
        assetId: "pub-master",
        name: "Scene 12B",
        startFrame: 0,
        durationFrames: 240,
        inPoint: 0,
        outPoint: 240,
        ingestRole: "published_master",
      },
    ];
    const text = createTextElement({ text: "QUARTERS INTERVIEW", startFrame: 48, endFrame: 168 });
    const lt = createLowerThirdGroup("ANADRIYA", "Current Adept");
    lt.startFrame = 120;
    lt.endFrame = 240;
    const merged = mergeGraphicsIntoSequence(doc, [text, lt]);
    expect(merged.tracks.some((track) => track.kind === "objects" && track.objectsSlot === 1)).toBe(true);
    expect(merged.clips.filter((clip) => clip.ingestRole === "published_master")).toHaveLength(1);
    const gfx = merged.clips.filter((clip) => isGraphicsClipId(clip.id));
    expect(gfx).toHaveLength(2);
    expect(gfx[0].id).toBe(`${GRAPHICS_CLIP_PREFIX}${text.id}`);
    expect(overlayIdFromGraphicsClip(gfx[0].id)).toBe(text.id);
    expect(gfx[0].startFrame).toBe(48);
    expect(gfx[0].durationFrames).toBe(120);
    expect(doc.clips).toHaveLength(1);
  });

  it("rebuilds projections instead of persisting leftover gfx clips", () => {
    const doc = createEmptySequence("proj-g", 24);
    const graphics = doc.tracks.find((track) => track.kind === "objects")!;
    doc.clips = [
      overlayToGraphicsClip(createTextElement({ id: "stale" }), graphics.id, 120),
    ];
    const next = createTextElement({ id: "fresh", startFrame: 10, endFrame: 40 });
    const merged = mergeGraphicsIntoSequence(doc, [next]);
    expect(merged.clips.map((clip) => clip.id)).toEqual([`${GRAPHICS_CLIP_PREFIX}fresh`]);
  });

  it("projects slot 2 overlays onto Objects 2 and strips gfx_* before persist", () => {
    const doc = createEmptySequence("proj-g", 24);
    const lt = createLowerThirdGroup("ANADRIYA", "Current Adept");
    lt.startFrame = 96;
    lt.endFrame = 216;
    const logo = createImageElement("logo-asset", {
      name: "Adept logo",
      objectsTrack: 2,
      startFrame: 0,
      endFrame: 720,
    });
    const merged = mergeGraphicsIntoSequence(doc, [lt, logo]);
    const o1 = findObjectsTrack(merged.tracks, 1)!;
    const o2 = findObjectsTrack(merged.tracks, 2)!;
    expect(o2.label).toBe("OBJECTS 2");
    const ltClip = merged.clips.find((clip) => clip.overlayId === lt.id)!;
    const logoClip = merged.clips.find((clip) => clip.overlayId === logo.id)!;
    expect(ltClip.trackId).toBe(o1.id);
    expect(logoClip.trackId).toBe(o2.id);
    expect(persistableSequenceClips(merged.clips)).toEqual([]);
    expect(persistableSequenceClips(merged.clips).every((clip) => !isGraphicsClipId(clip.id))).toBe(true);
  });
});
