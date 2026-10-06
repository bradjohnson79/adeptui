import { describe, expect, it } from "vitest";
import { createEmptySequence, type MagiClip } from "../../magiSequence/engine";
import { magiBoardDurationSec, magiSeekFrame, magiSkipFrame, magiTransportAt } from "./magiTransport";

function place(docId: string, id: string, trackId: string, startSec: number, durSec: number): MagiClip {
  const fps = 24;
  return {
    id,
    trackId,
    assetId: docId,
    name: id,
    startFrame: startSec * fps,
    durationFrames: durSec * fps,
    inPoint: 0,
    outPoint: durSec * fps,
  };
}

function scene() {
  const doc = createEmptySequence("proj", 24);
  const video = doc.tracks.find((track) => track.kind === "video");
  const audio = doc.tracks.find((track) => track.kind === "audio");
  if (!video || !audio) throw new Error("missing tracks");
  doc.clips = [
    place("a", "c1", video.id, 0, 15),
    place("a", "c2", video.id, 15, 15),
    place("a", "c3", video.id, 30, 15),
    place("a", "audio", audio.id, 0, 45),
  ];
  return doc;
}

describe("MAGI transport uses the Timeline board clock", () => {
  it("jumps inside the clip under the playhead and keeps scene end global", () => {
    const doc = scene();
    const at = magiTransportAt(doc, 20 * 24);
    expect(at.bounds.sceneStart).toBe(0);
    expect(at.bounds.sceneEnd).toBe(45);
    expect(at.piece?.id).toBe("c2");
    expect(at.bounds.activeBatchStart).toBe(15);
    expect(at.bounds.activeBatchEnd).toBe(30);
    expect(magiSeekFrame(doc, at.bounds.activeBatchStart)).toBe(15 * 24);
    expect(magiSeekFrame(doc, at.bounds.activeBatchEnd)).toBe(30 * 24);
    expect(magiSeekFrame(doc, 0)).toBe(0);
    expect(magiSeekFrame(doc, at.bounds.sceneEnd)).toBe(45 * 24);
  });

  it("clamps five-second skips to 0 and the real sequence end", () => {
    const doc = scene();
    expect(magiSkipFrame(doc, 3 * 24, -5)).toBe(0);
    expect(magiSkipFrame(doc, 42 * 24, 5)).toBe(45 * 24);
    expect(magiSkipFrame(doc, 20 * 24, 5)).toBe(25 * 24);
    expect(magiSkipFrame(doc, 20 * 24, -5)).toBe(15 * 24);
  });

  it("follows the Timeline gap rule and does not cap a two-minute sequence at 10 seconds", () => {
    const doc = createEmptySequence("proj", 24);
    const video = doc.tracks.find((track) => track.kind === "video");
    if (!video) throw new Error("missing video");
    doc.clips = [place("a", "early", video.id, 0, 10), place("a", "late", video.id, 20, 10)];
    const gap = magiTransportAt(doc, 15 * 24);
    expect(gap.piece?.id).toBe("early");
    expect(gap.bounds.activeBatchStart).toBe(0);
    expect(gap.bounds.activeBatchEnd).toBe(10);
    doc.clips = [place("a", "long", video.id, 0, 125)];
    expect(magiBoardDurationSec(doc)).toBe(125);
    expect(magiSeekFrame(doc, 90)).toBe(90 * 24);
    expect(magiBoardDurationSec(createEmptySequence("empty", 24))).toBe(10);
  });
});
