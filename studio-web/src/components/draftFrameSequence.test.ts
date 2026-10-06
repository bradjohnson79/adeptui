import { describe, expect, it } from "vitest";
import {
  appendDraftFrame,
  draftPlaybackMode,
  shouldResetDraftBuffer,
  DRAFT_SEQUENCE_MAX_FRAMES,
} from "./draftFrameSequence";

describe("draftFrameSequence", () => {
  it("appends unique URLs and dedupes consecutive duplicates", () => {
    let frames: string[] = [];
    frames = appendDraftFrame(frames, "a.png");
    frames = appendDraftFrame(frames, "a.png");
    frames = appendDraftFrame(frames, "b.png");
    expect(frames).toEqual(["a.png", "b.png"]);
  });

  it("caps buffer length", () => {
    let frames: string[] = [];
    for (let i = 0; i < DRAFT_SEQUENCE_MAX_FRAMES + 5; i++) {
      frames = appendDraftFrame(frames, `f${i}.png`);
    }
    expect(frames.length).toBe(DRAFT_SEQUENCE_MAX_FRAMES);
    expect(frames[0]).toBe("f5.png");
  });

  it("resets when leaving draft or switching jobs", () => {
    expect(shouldResetDraftBuffer({ showDraft: false, jobId: "1", prevJobId: "1" })).toBe(true);
    expect(shouldResetDraftBuffer({ showDraft: true, jobId: "2", prevJobId: "1" })).toBe(true);
    expect(shouldResetDraftBuffer({ showDraft: true, jobId: "1", prevJobId: "1" })).toBe(false);
  });

  it("playback mode is honest about frame count", () => {
    expect(draftPlaybackMode(0)).toBe("empty");
    expect(draftPlaybackMode(1)).toBe("still");
    expect(draftPlaybackMode(3)).toBe("sequence");
  });
});
