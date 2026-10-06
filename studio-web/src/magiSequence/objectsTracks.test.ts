import { describe, expect, it } from "vitest";
import { createEmptySequence } from "./engine";
import { persistableSequenceClips } from "./graphicsClips";
import {
  addOptionalObjectsTrack,
  canAddObjectsTrack,
  findObjectsTrack,
  removeOptionalObjectsTrack,
  visibleMagiTracks,
} from "./tracks";
import {
  compareOverlayPaintOrder,
  createImageElement,
  createLowerThirdGroup,
} from "../components/magi/overlays/types";

describe("MAGI Objects track contract", () => {
  it("never creates Objects 2 until + or a second layer is needed", () => {
    const doc = createEmptySequence("proj-o", 24);
    expect(findObjectsTrack(doc.tracks, 1)).toBeTruthy();
    expect(findObjectsTrack(doc.tracks, 2)).toBeUndefined();
    expect(canAddObjectsTrack(doc.tracks)).toBe(true);
  });

  it("adds Objects 2 above Objects 1 and refuses a third lane", () => {
    const withTwo = addOptionalObjectsTrack(createEmptySequence("proj-o", 24));
    expect(visibleMagiTracks(withTwo.tracks).map((track) => track.label)).toEqual([
      "OBJECTS 2",
      "OBJECTS 1",
      "VIDEO",
      "AUDIO",
      "MUSIC",
      "SFX",
    ]);
    expect(canAddObjectsTrack(withTwo.tracks)).toBe(false);
    expect(addOptionalObjectsTrack(withTwo)).toBe(withTwo);
  });

  it("remove Objects 2 drops the lane without deleting Objects 1", () => {
    const withTwo = addOptionalObjectsTrack(createEmptySequence("proj-o", 24));
    const next = removeOptionalObjectsTrack(withTwo);
    expect(findObjectsTrack(next.tracks, 2)).toBeUndefined();
    expect(findObjectsTrack(next.tracks, 1)).toBeTruthy();
    expect(visibleMagiTracks(next.tracks).map((track) => track.label)[0]).toBe("OBJECTS 1");
  });

  it("combined paint order is (objectsTrack, zIndex)", () => {
    const logo = createImageElement("logo", { objectsTrack: 2, zIndex: 1, name: "logo" });
    const lt = createLowerThirdGroup("ANADRIYA", "Current Adept");
    lt.objectsTrack = 1;
    lt.zIndex = 99;
    expect(compareOverlayPaintOrder(lt, logo)).toBeLessThan(0);
    const movedLt = { ...lt, objectsTrack: 2 as const, zIndex: 5 };
    const sameTrackLogo = { ...logo, zIndex: 10 };
    expect(compareOverlayPaintOrder(movedLt, sameTrackLogo)).toBeLessThan(0);
  });

  it("persistable clips never include gfx_* projections", () => {
    const clips = persistableSequenceClips([
      {
        id: "gfx_abc",
        trackId: "trk_objects_1",
        assetId: "overlay:abc",
        startFrame: 0,
        durationFrames: 24,
        inPoint: 0,
        outPoint: 24,
        ingestRole: "graphic",
      },
      {
        id: "clip_master",
        trackId: "trk_video",
        assetId: "pub",
        startFrame: 0,
        durationFrames: 24,
        inPoint: 0,
        outPoint: 24,
        ingestRole: "published_master",
      },
    ]);
    expect(clips.map((clip) => clip.id)).toEqual(["clip_master"]);
  });
});
