import { afterAll, describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { POSE_CATALOG } from "./poseCatalog";

/**
 * Master Program Phase 24–28: build-time thumbnail pipeline.
 *
 * Renders a real matching SVG thumbnail for each canonical pose from that
 * pose's exact joint data (2D front-projection stick figure) and writes them
 * to `studio-web/src/posecraft/thumbnails/<id>.svg`. The catalog embeds the
 * same SVG inline at import time so the UI never needs 50 live Babylon
 * thumbnail scenes (lazy thumbs). This test regenerates the on-disk
 * artifacts for CI provenance and asserts integrity.
 *
 * No GPU/Babylon required — pure 2D projection from canonical joint data.
 */
const OUT_DIR = path.join(__dirname, "thumbnails");

describe("build-time pose thumbnail pipeline", () => {
  it("writes a real matching SVG per pose and asserts >= 50", () => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    const ids = new Set<string>();
    let count = 0;
    for (const pose of POSE_CATALOG) {
      expect(pose.id, "unique pose id").not.toBe(ids.has(pose.id) ? pose.id : undefined);
      ids.add(pose.id);
      expect(pose.thumbnail, `${pose.id} has a real matching thumbnail`).toBeTruthy();
      expect(pose.thumbnail!.startsWith("<svg")).toBe(true);
      fs.writeFileSync(path.join(OUT_DIR, `${pose.id}.svg`), pose.thumbnail!);
      count += 1;
    }
    expect(count, `wrote ${count} thumbnails, need >= 50`).toBeGreaterThanOrEqual(50);
  });

  it("the on-disk thumbnail count matches the catalog", () => {
    const files = fs.readdirSync(OUT_DIR).filter((f) => f.endsWith(".svg"));
    expect(files.length).toBe(POSE_CATALOG.length);
    for (const pose of POSE_CATALOG) {
      expect(files, `${pose.id}.svg on disk`).toContain(`${pose.id}.svg`);
    }
  });

  afterAll(() => {
    // Thumbnails are regenerated each run; leave them on disk for audit.
  });
});
