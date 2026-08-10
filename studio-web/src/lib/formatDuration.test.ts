import { describe, expect, it } from "vitest";
import { formatDurationSeconds, formatJobTimestamp } from "./formatDuration";

describe("formatDurationSeconds", () => {
  it("rounds raw floats to two decimals", () => {
    expect(formatDurationSeconds(5.004000000000001)).toBe("5.00 s");
  });
});

describe("formatJobTimestamp", () => {
  it("parses naive API timestamps as UTC and renders local time", () => {
    const out = formatJobTimestamp("2026-08-07 07:20:49.744948");
    expect(out).not.toBe("");
    // Locale-rendered: contains month + day + time, and is timezone-shifted
    // away from the raw UTC wall-clock string for non-UTC machines.
    expect(out).toMatch(/Aug/);
    expect(out).toMatch(/7/);
    expect(out).toMatch(/\d{1,2}:\d{2}/);
  });

  it("accepts ISO timestamps with timezone markers unchanged", () => {
    const a = formatJobTimestamp("2026-08-07T07:20:49Z");
    expect(a).toMatch(/Aug/);
  });

  it("returns empty string for missing or unparseable values", () => {
    expect(formatJobTimestamp(null)).toBe("");
    expect(formatJobTimestamp(undefined)).toBe("");
    expect(formatJobTimestamp("")).toBe("");
    expect(formatJobTimestamp("not-a-date")).toBe("");
  });
});
