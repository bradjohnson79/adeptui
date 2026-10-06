import { describe, expect, it } from "vitest";
import {
  aspectsMatch,
  defaultTargetId,
  isAboveSource,
  meaningfulTargets,
  preferredPublishSource,
  resolveUpscaleTarget,
} from "./magiUpscaleTargets";

describe("MAGI meaningful upscale targets", () => {
  it("refuses 1080p → 1080p and keeps 16:9 at higher classes", () => {
    expect(isAboveSource(1920, 1080, 1920, 1080)).toBe(false);
    expect(meaningfulTargets(1920, 1080).map((t) => t.id)).toEqual(["1440p", "2K", "4K", "8K"]);
    expect(defaultTargetId(1920, 1080)).toBe("1440p");
    expect(resolveUpscaleTarget(1920, 1080, "1440p")).toMatchObject({ width: 2560, height: 1440, aspect: "16:9" });
    expect(resolveUpscaleTarget(1920, 1080, "4K")).toMatchObject({ width: 3840, height: 2160, aspect: "16:9" });
  });

  it("offers 1080p and up from 720p", () => {
    expect(meaningfulTargets(1280, 720).map((t) => t.id)).toEqual(["1080p", "1440p", "2K", "4K", "8K"]);
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

  it("portrait sources keep their ratio instead of a swapped 16:9 canvas", () => {
    const rows = meaningfulTargets(704, 1248);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((t) => t.height > t.width)).toBe(true);
    expect(rows[0].id).toBe("1080p");
    expect(rows[0]).not.toMatchObject({ width: 1080, height: 1920 });
    expect(aspectsMatch(704, 1248, rows[0].width, rows[0].height)).toBe(true);
    expect(isAboveSource(704, 1248, 1920, 1080)).toBe(false);
  });

  it("21:9 1440p, 2K, and 4K stay ultrawide", () => {
    const source = { w: 1568, h: 672 };
    for (const id of ["1440p", "2K", "4K"]) {
      const row = resolveUpscaleTarget(source.w, source.h, id);
      expect(row.aspect).toBe("21:9");
      expect(aspectsMatch(source.w, source.h, row.width, row.height)).toBe(true);
      expect(row.width / row.height).toBeGreaterThan(2.2);
      expect(row).not.toMatchObject({ width: 2560, height: 1440 });
    }
    expect(resolveUpscaleTarget(source.w, source.h, "1440p")).toMatchObject({ width: 3360, height: 1440 });
  });

  it("a nonstandard ratio is not snapped to 16:9", () => {
    const row = resolveUpscaleTarget(1000, 777, "1440p");
    expect(aspectsMatch(1000, 777, row.width, row.height)).toBe(true);
    expect(row.aspect).not.toBe("16:9");
  });
});
