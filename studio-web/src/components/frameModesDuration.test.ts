/**
 * FrameModes no-write-back law (Timeline UX root fix, item 2 Layer 3).
 *
 * MiniMax H3 runs on a 17k+5 frame grid. The snap is REQUEST-scoped: the
 * backend builder (h3_ref2v_builder / request_builder._h3_duration_for_request)
 * snaps at generation time and discloses. The 1 Frame / First-Last-Frame
 * Generate handlers must persist the canvas only and must NEVER write a
 * snapped duration back onto the scene row (regression: Scene 7 once held
 * duration_sec=7.291666666666667 from a 7.0s creator request).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const src = readFileSync(resolve(__dirname, "FrameModes.tsx"), "utf8");

describe("FrameModes H3 snap is request-scoped (no scene write-back)", () => {
  it("never computes a snapped submit duration", () => {
    expect(src).not.toMatch(/submitDurationSec/);
    expect(src).not.toMatch(/h3LegalDurationSeconds/);
  });

  it("1F and FLF Generate persist canvas only (no duration_sec override)", () => {
    const canvasOnlyPersist =
      /await api\.updateScene\(project\.id, scene\.id, \{\s*\.\.\.scene,\s*width: canvas\.width,\s*height: canvas\.height,\s*\}\);/g;
    const matches = src.match(canvasOnlyPersist);
    // Exactly the 1 Frame and First-Last-Frame Generate handlers.
    expect(matches).toHaveLength(2);
    // Those are also the only two Generate (api.render) paths in the file,
    // so no generation path can persist a snapped duration.
    expect(src.match(/await api\.render\(/g)).toHaveLength(2);
  });
});
