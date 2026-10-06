import { describe, expect, it } from "vitest";
import { formatAudioClock } from "./VoiceSamplePlayers";

describe("formatAudioClock", () => {
  it("formats finite seconds as m:ss", () => {
    expect(formatAudioClock(0)).toBe("0:00");
    expect(formatAudioClock(9)).toBe("0:09");
    expect(formatAudioClock(75)).toBe("1:15");
  });

  it("treats missing duration as 0:00", () => {
    expect(formatAudioClock(Number.NaN)).toBe("0:00");
    expect(formatAudioClock(-1)).toBe("0:00");
  });
});
