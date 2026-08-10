import { describe, expect, it } from "vitest";
import {
  applyEditCommand,
  createEmptySequence,
  type MagiClip,
  type MagiSequenceDocument,
} from "./engine";

function seededSequence(): MagiSequenceDocument {
  const doc = createEmptySequence("proj-a", 24);
  doc.tracks = [
    { id: "trk_v1", kind: "video", label: "V1", order: 0 },
    { id: "trk_v2", kind: "video", label: "V2", order: 1 },
  ];
  const base: MagiClip = {
    id: "clip_000001",
    trackId: "trk_v1",
    assetId: "asset_1",
    name: "Shot",
    startFrame: 0,
    durationFrames: 24,
    inPoint: 0,
    outPoint: 24,
    // m5 lineage from a W46 timeline import.
    batchBlockId: "bb_1234",
    generationId: "gen_1",
    takeId: "tk_1",
    sourceClipId: "src_orig",
    sceneId: "scene_x",
  };
  doc.clips = [base];
  return doc;
}

function findClip(doc: MagiSequenceDocument, id: string): MagiClip {
  const clip = doc.clips.find((c) => c.id === id);
  if (!clip) throw new Error(`missing clip ${id}`);
  return clip;
}

describe("engine command lineage + id integrity (m4/m1 A6)", () => {
  it("preserves W46 lineage fields and id on Move", () => {
    const doc = seededSequence();
    const { doc: next } = applyEditCommand(doc, { kind: "Move", payload: { clipId: "clip_000001", startFrame: 48 } }, []);
    const clip = findClip(next, "clip_000001");
    expect(clip.startFrame).toBe(48);
    expect(clip.batchBlockId).toBe("bb_1234");
    expect(clip.generationId).toBe("gen_1");
    expect(clip.takeId).toBe("tk_1");
    expect(clip.sourceClipId).toBe("src_orig");
    expect(clip.sceneId).toBe("scene_x");
    expect(next.clips.length).toBe(1);
  });

  it("preserves lineage and assigns a unique new id on Duplicate", () => {
    const doc = seededSequence();
    const { doc: next, selection } = applyEditCommand(doc, { kind: "Duplicate", payload: { offsetFrames: 24 } }, ["clip_000001"]);
    expect(next.clips.length).toBe(2);
    const [original, copy] = next.clips;
    expect(original.id).toBe("clip_000001");
    expect(copy.id).not.toBe("clip_000001");
    expect(new Set(next.clips.map((c) => c.id)).size).toBe(2);
    expect(copy.batchBlockId).toBe("bb_1234");
    expect(copy.generationId).toBe("gen_1");
    expect(copy.sourceClipId).toBe("src_orig");
    expect(copy.sceneId).toBe("scene_x");
    expect(selection).toEqual([copy.id]);
  });

  it("Split produces a new right-hand clip with lineage and unique id", () => {
    const doc = seededSequence();
    const { doc: next, selection } = applyEditCommand(doc, { kind: "Split", payload: { clipId: "clip_000001", frame: 12 } }, []);
    expect(next.clips.length).toBe(2);
    const ids = next.clips.map((c) => c.id);
    expect(ids).toContain("clip_000001");
    expect(new Set(ids).size).toBe(2);
    for (const clip of next.clips) {
      expect(clip.batchBlockId).toBe("bb_1234");
      expect(clip.generationId).toBe("gen_1");
      expect(clip.takeId).toBe("tk_1");
      expect(clip.sourceClipId).toBe("src_orig");
      expect(clip.sceneId).toBe("scene_x");
    }
    expect(selection.length).toBe(2);
  });

  it("Delete removes the clip and clears selection", () => {
    const doc = seededSequence();
    const { doc: next, selection } = applyEditCommand(doc, { kind: "RippleDelete" }, ["clip_000001"]);
    expect(next.clips.length).toBe(0);
    expect(selection).toEqual([]);
  });

  it("AddMarker appends a marker without touching clip lineage", () => {
    const doc = seededSequence();
    const { doc: next } = applyEditCommand(doc, { kind: "AddMarker", payload: { frame: 10, label: "beat" } }, []);
    expect(next.markers.length).toBe(1);
    expect(next.markers[0].frame).toBe(10);
    expect(findClip(next, "clip_000001").sourceClipId).toBe("src_orig");
  });

  it("SetPlayhead updates transport without adding clips or lineage churn", () => {
    const doc = seededSequence();
    const { doc: next } = applyEditCommand(doc, { kind: "SetPlayhead", payload: { frame: 30 } }, []);
    expect(next.playheadFrame).toBe(30);
    expect(next.clips).toHaveLength(1);
  });

  it("Trim preserves lineage on the trimmed clip", () => {
    const doc = seededSequence();
    const { doc: next } = applyEditCommand(doc, { kind: "Trim", payload: { clipId: "clip_000001", edge: "right", deltaFrames: -4 } }, []);
    const clip = findClip(next, "clip_000001");
    expect(clip.durationFrames).toBe(20);
    expect(clip.batchBlockId).toBe("bb_1234");
    expect(clip.sourceClipId).toBe("src_orig");
  });
});
