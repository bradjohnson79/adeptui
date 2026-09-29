import { describe, expect, it } from "vitest";
import {
  TIMELINE_AUDIO_FILE_ACCEPT,
  applySelectedAudioFile,
  audioClipMetadata,
  blankAudioClipDraft,
  filenameStem,
  laneTimeFromPointer,
  textFromAudioMetadata,
} from "./audioClipModal";

describe("audio clip modal", () => {
  it("accepts only the formats the asset pipeline already treats as audio", () => {
    expect(TIMELINE_AUDIO_FILE_ACCEPT.split(",")).toEqual([
      ".wav",
      ".mp3",
      ".ogg",
      ".flac",
      ".m4a",
      ".aac",
    ]);
  });

  it("uses the file name as a title and the real duration as length", () => {
    const next = applySelectedAudioFile(blankAudioClipDraft("audio", 14.5), "cafe-room.wav", 7.38);
    expect(next.start).toBe(14.5);
    expect(next.length).toBe(7.38);
    expect(next.title).toBe("cafe-room");
    expect(next.label).toBe("cafe-room");
    expect(next.description).toBe("");
    expect(filenameStem("cafe-room.wav")).toBe("cafe-room");
  });

  it("does not invent a description or replace a title the creator already typed", () => {
    const started = { ...blankAudioClipDraft("sfx", 0), title: "Door", description: "" };
    const next = applySelectedAudioFile(started, "hit.wav", 1.25);
    expect(next.title).toBe("Door");
    expect(next.description).toBe("");
    expect(next.length).toBe(1.25);
  });

  it("reads the lane time from the pointer the Timeline already uses", () => {
    expect(laneTimeFromPointer(150, { left: 100, width: 200 }, 45)).toBe(11.25);
    expect(laneTimeFromPointer(100, { left: 100, width: 450 }, 45)).toBe(0);
  });

  it("stores title and description on the clip metadata the Inspector reads", () => {
    const metadata = audioClipMetadata({ title: "Room", description: "Soft murmur", metadata: { keep: true } });
    expect(textFromAudioMetadata(metadata, "title")).toBe("Room");
    expect(textFromAudioMetadata(metadata, "description")).toBe("Soft murmur");
    expect(metadata.keep).toBe(true);
  });
});
