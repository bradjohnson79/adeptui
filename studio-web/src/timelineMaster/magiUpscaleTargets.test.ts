import { describe, expect, it } from "vitest";
import {
  defaultTargetId,
  isAboveSource,
  meaningfulTargets,
  preferredPublishSource,
} from "./magiUpscaleTargets";

describe("MAGI meaningful upscale targets", () => {
  it("refuses 1080p → 1080p", () => {
    expect(isAboveSource(1920, 1080, 1920, 1080)).toBe(false);
    expect(meaningfulTargets(1920, 1080).map((t) => t.id)).toEqual(["1440p", "4K", "8K"]);
    expect(defaultTargetId(1920, 1080)).toBe("1440p");
  });

  it("offers 1080p and up from 720p", () => {
    expect(meaningfulTargets(1280, 720).map((t) => t.id)).toEqual(["1080p", "1440p", "4K", "8K"]);
    expect(defaultTargetId(1280, 720)).toBe("1080p");
  });

  it("offers only 8K from 4K", () => {
    expect(meaningfulTargets(3840, 2160).map((t) => t.id)).toEqual(["8K"]);
  });

  it("has no higher target at 8K", () => {
    expect(meaningfulTargets(7680, 4320)).toEqual([]);
    expect(defaultTargetId(7680, 4320)).toBe("");
  });

  it("publishes the MAGI derivative when one exists", () => {
    expect(preferredPublishSource("up-1")).toBe("upscaled");
    expect(preferredPublishSource("")).toBe("stitch");
    expect(preferredPublishSource(null)).toBe("stitch");
  });

  it("portrait 9:16 sources get portrait targets, never 1920x1080", () => {
    const rows = meaningfulTargets(704, 1248);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((t) => t.height > t.width)).toBe(true);
    expect(rows[0]).toMatchObject({ id: "1080p", width: 1080, height: 1920 });
    expect(isAboveSource(704, 1248, 1920, 1080)).toBe(false);
  });
});
