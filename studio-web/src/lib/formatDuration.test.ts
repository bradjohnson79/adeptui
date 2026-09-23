import { describe, expect, it } from "vitest";
import { formatDurationSeconds, formatJobTimestamp } from "./formatDuration";

describe("formatDurationSeconds", () => {
  it("renders whole seconds without float garbage", () => {
    expect(formatDurationSeconds(15)).toBe("15s");
    expect(formatDurationSeconds(15.0)).toBe("15s");
    expect(formatDurationSeconds(5.000000000000001)).toBe("5s");
  });

  it("renders frame-derived floats as one clean decimal", () => {
    expect(formatDurationSeconds(5.166666666666667)).toBe("5.2s");
    expect(formatDurationSeconds(7.291666666666667)).toBe("7.3s");
  });

  it("returns em dash for missing values", () => {
    expect(formatDurationSeconds(null)).toBe("—");
    expect(formatDurationSeconds(undefined)).toBe("—");
    expect(formatDurationSeconds(Number.NaN)).toBe("—");
  });
});

describe("formatJobTimestamp", () => {
  it("parses naive API timestamps as UTC and renders local time", () => {
    const out = formatJobTimestamp("2026-08-07 07:20:49.744948");
    expect(out).not.toBe("");
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
