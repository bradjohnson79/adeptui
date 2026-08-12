// @ts-check
/**
 * Build-time thumbnail pipeline for the PoseCraft pose catalog (Master Program
 * Phase 24–28 / image pipeline).
 *
 * Renders a real matching SVG thumbnail for each canonical pose from that
 * pose's exact joint data (2D front-projection stick figure), and writes them
 * to `studio-web/src/posecraft/thumbnails/<id>.svg`. The catalog module also
 * embeds the same SVG strings inline at import time (so the UI never needs 50
 * live Babylon thumbnail scenes); this script is the offline generator that
 * regenerates the on-disk artifacts for auditing / CI provenance.
 *
 * Run: node --experimental-strip-types scripts/build-pose-thumbnails.mjs
 *
 * (No GPU/Babylon required — pure 2D projection from canonical joint data.)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { POSE_CATALOG } from "../studio-web/src/posecraft/poseCatalog.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "studio-web", "src", "posecraft", "thumbnails");

fs.mkdirSync(OUT_DIR, { recursive: true });
let count = 0;
const ids = new Set();
for (const pose of POSE_CATALOG) {
  if (ids.has(pose.id)) {
    throw new Error(`Duplicate pose id in catalog: ${pose.id}`);
  }
  ids.add(pose.id);
  if (!pose.thumbnail || !pose.thumbnail.startsWith("<svg")) {
    throw new Error(`Pose ${pose.id} missing real matching thumbnail`);
  }
  fs.writeFileSync(path.join(OUT_DIR, `${pose.id}.svg`), pose.thumbnail);
  count += 1;
}
if (count < 50) {
  throw new Error(`Thumbnail pipeline produced ${count} thumbnails; need >= 50`);
}
console.log(`Wrote ${count} pose thumbnails to ${OUT_DIR}`);
