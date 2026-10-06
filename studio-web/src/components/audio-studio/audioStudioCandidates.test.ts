import { describe, expect, it } from "vitest";
import { approvedIdsFromBatches, classifyLibraryAudio, extractCandidates, latestBatchForKind } from "./audioStudioCandidates";

describe("Audio Studio candidate authority", () => {
  it("does not invent candidates from leftover Library assets", () => {
    expect(extractCandidates({ candidates: [] }, "music")).toEqual([]);
  });

  it("keeps the newest batch for a kind and ignores other kinds", () => {
    const latest = latestBatchForKind(
      [
        { id: "old", method: "music", created_at: "2026-01-01" },
        { id: "sfx", method: "sfx", created_at: "2026-09-01" },
        { id: "new", method: "music", created_at: "2026-09-01" },
      ],
      "music",
    );
    expect(latest?.id).toBe("new");
  });

  it("records approved asset ids from persisted batches", () => {
    expect(
      approvedIdsFromBatches([
        { candidates: [{ status: "approved", asset_id: "a1" }, { status: "ready", asset_id: "a2" }] },
      ]),
    ).toEqual({ a1: true });
  });

  it("classifies project audio without creating a second library", () => {
    expect(classifyLibraryAudio({ tag: "ambience-corridor" })).toBe("ambience");
    expect(classifyLibraryAudio({ libraryKey: "audio.voice" })).toBe("voice");
    expect(classifyLibraryAudio({ title: "Korri Clone" })).toBe("audio");
  });
});
