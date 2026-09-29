import { describe, expect, it } from "vitest";
import {
  SAME_TRACK_EPS,
  SameTrackOverlapError,
  assertNoSameTrackOverlap,
  audioLaneKind,
  CD_LAYMAN_TRACK_OCCUPIED,
  findSameTrackIntersection,
  findSameTrackOverlapPair,
  firstFreeSameTrackStart,
  rangesIntersect,
  sameTrackOverlapError,
  USER_FACING_TRACK_OCCUPIED,
} from "./sameTrackNoOverlap";

describe("rangesIntersect", () => {
  it("is false for adjacent boundaries (A.end == B.start)", () => {
    expect(rangesIntersect(0, 10, 10, 10)).toBe(false);
    expect(rangesIntersect(10, 10, 0, 10)).toBe(false);
  });

  it("is true for open overlap", () => {
    expect(rangesIntersect(0, 10, 0, 10)).toBe(true);
    expect(rangesIntersect(0, 10, 5, 5)).toBe(true);
    expect(rangesIntersect(0, 9.938, 0, 10)).toBe(true);
  });

  it("is false when ranges are separated", () => {
    expect(rangesIntersect(0, 5, 6, 2)).toBe(false);
  });

  it("treats sub-epsilon overlap as adjacent (same law as Python)", () => {
    expect(rangesIntersect(0, 10, 10 - SAME_TRACK_EPS / 2, 4)).toBe(false);
    expect(rangesIntersect(0, 10, 10 - 1e-6, 4)).toBe(true);
  });
});

describe("findSameTrackIntersection", () => {
  const clips = [
    { id: "keep", start: 0, length: 10 },
    { id: "later", start: 10, length: 10 },
  ];

  it("returns null for adjacent insert after last", () => {
    expect(findSameTrackIntersection(clips, { id: "new", start: 20, length: 5 })).toBeNull();
  });

  it("finds overlap at start 0 against an occupant", () => {
    const hit = findSameTrackIntersection(clips, { id: "new", start: 0, length: 2 });
    expect(hit?.id).toBe("keep");
  });

  it("excludes the same id (move/resize of self)", () => {
    expect(findSameTrackIntersection(clips, { id: "keep", start: 0, length: 10 })).toBeNull();
  });

  it("Scene 10 illegal stack: two BGM + misfiled SFX all at 0", () => {
    const stacked = [
      { id: "clip_omni_music_bd13b3", start: 0, length: 9.938 },
      { id: "clip_omni_sfx_bd13b3", start: 0, length: 0.15 },
      { id: "clip_430c79f36a18", start: 0, length: 10 },
    ];
    const pair = findSameTrackOverlapPair(stacked);
    expect(pair).not.toBeNull();
    expect(pair?.a.id).toBe("clip_omni_music_bd13b3");
    expect(pair?.b.id).toBe("clip_omni_sfx_bd13b3");
  });
});

describe("firstFreeSameTrackStart", () => {
  it("uses time 0 when the lane is empty", () => {
    expect(firstFreeSameTrackStart([], 2, 45)).toBe(0);
  });

  it("steps past an occupant at time 0", () => {
    expect(firstFreeSameTrackStart([{ id: "a", start: 0, length: 2 }], 2, 45)).toBe(2);
  });

  it("returns null when the clip cannot fit", () => {
    expect(firstFreeSameTrackStart([{ id: "a", start: 0, length: 45 }], 2, 45)).toBeNull();
  });
});

describe("assertNoSameTrackOverlap", () => {
  it("returns no error when the lane is free", () => {
    expect(sameTrackOverlapError([], { id: "n", start: 0, length: 2 })).toBeNull();
    expect(() => assertNoSameTrackOverlap([], { id: "n", start: 0, length: 2 })).not.toThrow();
  });

  it("throws SAME_TRACK_OVERLAP when occupied", () => {
    expect(() =>
      assertNoSameTrackOverlap([{ id: "keep", start: 0, length: 10 }], { id: "n", start: 0, length: 2 }, "audio"),
    ).toThrow(SameTrackOverlapError);
    const message = sameTrackOverlapError([{ id: "keep", start: 0, length: 10 }], { id: "n", start: 0, length: 2 }, "audio");
    expect(message).toContain("SAME_TRACK_OVERLAP");
    expect(message).toContain("audio");
  });

  it("aliases music/ambience to the Audio lane", () => {
    expect(audioLaneKind("music")).toBe("audio");
    expect(audioLaneKind("ambience")).toBe("audio");
    expect(audioLaneKind("audio")).toBe("audio");
    expect(audioLaneKind("sfx")).toBe("sfx");
  });
});

describe("UX copy", () => {
  it("exposes creator and CD layman strings without raw codes", () => {
    expect(USER_FACING_TRACK_OCCUPIED.toLowerCase()).toContain("occupied");
    expect(CD_LAYMAN_TRACK_OCCUPIED.toLowerCase()).toContain("already in use");
    expect(CD_LAYMAN_TRACK_OCCUPIED).not.toContain("SAME_TRACK");
  });
});

describe("timed prompt edge cases", () => {
  it("allows 0-5 + 5-10 and rejects 0-5 + 4.9-10", () => {
    expect(rangesIntersect(0, 5, 5, 5)).toBe(false);
    expect(rangesIntersect(0, 5, 4.9, 5.1)).toBe(true);
    expect(
      findSameTrackIntersection(
        [{ id: "a", start: 0, length: 5 }],
        { id: "b", start: 5, length: 5 },
      ),
    ).toBeNull();
    expect(
      findSameTrackIntersection(
        [{ id: "a", start: 0, length: 5 }],
        { id: "b", start: 4.9, length: 5.1 },
      )?.id,
    ).toBe("a");
  });
});
