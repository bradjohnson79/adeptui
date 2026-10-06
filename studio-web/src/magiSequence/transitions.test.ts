import { describe, expect, it } from "vitest";
import { createEmptySequence, type MagiClip } from "./engine";
import {
  adjacencyToleranceFrames,
  blendAtPlayhead,
  blendSourceSeconds,
  clipEdgeRole,
  cutLayerPresentation,
  edgeFadeAtPlayhead,
  maxEdgeFadeSeconds,
  transitionPreviewFrame,
  maxTransitionSeconds,
  resolveOutgoingCut,
} from "./transitions";

function clip(partial: Partial<MagiClip> & Pick<MagiClip, "id" | "startFrame" | "durationFrames">): MagiClip {
  return {
    trackId: "trk_v",
    assetId: "asset",
    name: partial.id,
    inPoint: 0,
    outPoint: partial.durationFrames,
    ...partial,
  };
}

function docWith(clips: MagiClip[], kinds: Array<{ id: string; kind: "video" | "audio" | "objects" }> = [{ id: "trk_v", kind: "video" }]) {
  const doc = createEmptySequence("proj", 24);
  doc.tracks = kinds.map((track, order) => ({ id: track.id, kind: track.kind, label: track.kind, order }));
  doc.clips = clips;
  return doc;
}

describe("MAGI cut resolution", () => {
  it("treats an exact meet as a cut and a 2s gap as unavailable", () => {
    const left = clip({ id: "a", name: "Clip A", startFrame: 0, durationFrames: 360 });
    const meeting = clip({ id: "b", name: "Clip B", startFrame: 360, durationFrames: 360 });
    const exact = docWith([left, meeting]);
    const cut = resolveOutgoingCut(exact, left);
    expect(cut.status).toBe("cut");
    if (cut.status === "cut") {
      expect(cut.next.id).toBe("b");
      expect(cut.cutFrame).toBe(360);
      expect(cut.maxSeconds).toBeGreaterThanOrEqual(0.1);
    }

    const gapped = docWith([
      left,
      clip({ id: "b", startFrame: 360 + 48, durationFrames: 360 }),
    ]);
    expect(resolveOutgoingCut(gapped, left).status).toBe("gap");
    expect(resolveOutgoingCut(gapped, gapped.clips[1]).status).toBe("last");
  });

  it("uses the timeline snap window and ignores audio cuts", () => {
    expect(adjacencyToleranceFrames(24)).toBe(5);
    const left = clip({ id: "a", startFrame: 0, durationFrames: 100 });
    const near = docWith([left, clip({ id: "b", startFrame: 104, durationFrames: 100 })]);
    expect(resolveOutgoingCut(near, left).status).toBe("cut");
    const far = docWith([left, clip({ id: "b", startFrame: 106, durationFrames: 100 })]);
    expect(resolveOutgoingCut(far, left).status).toBe("gap");

    const audio = docWith(
      [clip({ id: "a", trackId: "trk_a", startFrame: 0, durationFrames: 100 }), clip({ id: "b", trackId: "trk_a", startFrame: 100, durationFrames: 100 })],
      [{ id: "trk_a", kind: "audio" }],
    );
    expect(resolveOutgoingCut(audio, audio.clips[0]).status).toBe("not-picture");
  });

  it("keeps fade through black distinct from dissolve and centers the blend on the cut", () => {
    expect(cutLayerPresentation("dissolve", 0.5)).toEqual({ outgoingOpacity: 1, incomingOpacity: 0.5 });
    expect(cutLayerPresentation("fade", 0.2)).toEqual({ outgoingOpacity: 0, incomingOpacity: 0 });
    expect(cutLayerPresentation("fade", 0.5).outgoingOpacity).toBe(0);
    expect(cutLayerPresentation("fade", 0.5).incomingOpacity).toBeCloseTo(0.375);
    expect(cutLayerPresentation("wipe", 0.5).incomingClipPath).toBe("inset(0 0 0 50%)");
    expect(maxTransitionSeconds(24, 24, 24)).toBe(0.9);

    const left = clip({
      id: "a",
      startFrame: 0,
      durationFrames: 240,
      transitionOutId: "dissolve",
      transitionDurationFrames: 24,
    });
    const right = clip({ id: "b", startFrame: 240, durationFrames: 240, inPoint: 240, outPoint: 480 });
    const sequence = docWith([left, right]);
    const before = blendAtPlayhead(sequence, 240 - 12);
    const mid = blendAtPlayhead(sequence, 240);
    const after = blendAtPlayhead(sequence, 240 + 12);
    const outside = blendAtPlayhead(sequence, 200);
    expect(before?.progress).toBeCloseTo(0, 1);
    expect(mid?.progress).toBeCloseTo(0.5, 1);
    expect(after?.progress).toBeCloseTo(1, 1);
    expect(outside).toBeNull();
    expect(blendSourceSeconds(right, 230, 24)).toBeCloseTo(240 / 24);
    expect(blendSourceSeconds(left, 250, 24)).toBeCloseTo(239 / 24);
  });

  it("fades the open start and end without replacing the cut between clips", () => {
    const first = clip({
      id: "a",
      startFrame: 0,
      durationFrames: 240,
      transitionInId: "fade",
      transitionInDurationFrames: 24,
      transitionOutId: "dissolve",
      transitionDurationFrames: 24,
    });
    const last = clip({
      id: "b",
      startFrame: 240,
      durationFrames: 240,
      transitionOutId: "fade",
      transitionDurationFrames: 24,
    });
    const sequence = docWith([first, last]);
    expect(clipEdgeRole(sequence, first)).toEqual({ first: true, last: false });
    expect(clipEdgeRole(sequence, last)).toEqual({ first: false, last: true });
    expect(resolveOutgoingCut(sequence, first).status).toBe("cut");
    expect(resolveOutgoingCut(sequence, last).status).toBe("last");
    expect(maxEdgeFadeSeconds(240, 24)).toBeGreaterThanOrEqual(0.1);
    expect(edgeFadeAtPlayhead(sequence, 0)?.opacity).toBe(0);
    expect(edgeFadeAtPlayhead(sequence, 12)?.opacity).toBeCloseTo(0.5);
    expect(edgeFadeAtPlayhead(sequence, 48)).toBeNull();
    expect(edgeFadeAtPlayhead(sequence, 240 + 240 - 12)?.opacity).toBeCloseTo(0.5);
    expect(edgeFadeAtPlayhead(sequence, 240 + 100)).toBeNull();
  });

  it("parks the playhead inside a transition the moment it is applied", () => {
    const tail = clip({ id: "tail", startFrame: 240, durationFrames: 240 });
    expect(
      transitionPreviewFrame({
        playheadFrame: 240,
        clip: tail,
        durationFrames: 24,
        edge: "out",
      }),
    ).toBe(240 + 240 - 12);
    expect(
      transitionPreviewFrame({
        playheadFrame: 240 + 240 - 4,
        clip: tail,
        durationFrames: 24,
        edge: "out",
      }),
    ).toBeNull();
    expect(
      transitionPreviewFrame({
        playheadFrame: 0,
        clip: clip({ id: "head", startFrame: 0, durationFrames: 240 }),
        durationFrames: 24,
        edge: "in",
      }),
    ).toBeNull();
    expect(
      transitionPreviewFrame({
        playheadFrame: 400,
        clip: clip({ id: "left", startFrame: 0, durationFrames: 240 }),
        durationFrames: 24,
        edge: "out",
        cutFrame: 240,
      }),
    ).toBe(240);
  });
});
