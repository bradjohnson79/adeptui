import { describe, expect, it } from "vitest";
import {
  clipsOverflowGeneratorMax,
  creatorGeneratorLine,
  farthestClipEnd,
  generatorMaxDurationSec,
  timelineBoardDurationSec,
  trimClipsToDuration,
} from "./generatorDuration";

describe("generator duration", () => {
  it("detects overflow without inventing a trim", () => {
    const clips = [
      { start: 0, length: 5 },
      { start: 4, length: 3 },
    ];
    expect(farthestClipEnd(clips)).toBe(7);
    expect(clipsOverflowGeneratorMax(clips, 5)).toBe(true);
    expect(clipsOverflowGeneratorMax(clips, 8)).toBe(false);
    expect(clipsOverflowGeneratorMax(clips, null)).toBe(false);
  });

  it("trims to scene only when asked", () => {
    const next = trimClipsToDuration(
      [
        { start: 0, length: 5, id: "keep" },
        { start: 4, length: 3, id: "trim" },
        { start: 6, length: 2, id: "drop" },
      ],
      5,
    );
    expect(next.map((c) => ({ id: c.id, start: c.start, length: c.length }))).toEqual([
      { id: "keep", start: 0, length: 5 },
      { id: "trim", start: 4, length: 1 },
    ]);
  });

  it("uses live max duration, not a prompt number", () => {
    expect(
      creatorGeneratorLine({
        label: "MiniMax H3 Text-to-Video (Local)",
        executionType: "local",
        maxDurationSec: 5,
      }),
    ).toBe("MiniMax H3 Text-to-Video — Local · 5s");
    expect(generatorMaxDurationSec({ supportedDurations: [5, 8, 20] })).toBe(20);
  });

  it("uses the sum of batch windows as the board clock", () => {
    expect(
      timelineBoardDurationSec(
        { batchBlocks: [{ duration: { plannedDuration: 5 } }, { duration: { plannedDuration: 5 } }] },
        { duration_sec: 5 },
        { duration_sec: 5 },
      ),
    ).toBe(10);
    expect(timelineBoardDurationSec(null, { duration_sec: 8 }, { duration_sec: 5 })).toBe(8);
  });
});
