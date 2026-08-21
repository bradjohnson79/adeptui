/**
 * Exports the canonical PoseCraft pose catalog (joint data only, no
 * thumbnails) to studio-api/app/posecraft/pose_catalog.json so the
 * Co-Director `posecraft.apply_pose` handler can resolve presets
 * server-side from the same source of truth.
 *
 * Run: npx vite-node scripts/export-pose-catalog.ts
 * A vitest contract test (poseCatalogExport.test.ts) fails if the export
 * drifts from POSE_CATALOG, so the TS catalog stays the single source.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { POSE_CATALOG } from "../src/posecraft/poseCatalog";
import { JOINT_LIMITS } from "../src/posecraft/constants";

export function buildCatalogExport() {
  return {
    schema: "posecraft-pose-catalog@1",
    jointLimits: JOINT_LIMITS,
    poses: POSE_CATALOG.map((p) => ({
      id: p.id,
      label: p.label,
      category: p.category,
      description: p.description,
      archetypes: p.archetypes ?? null,
      joints: p.joints,
    })),
  };
}

const target = resolve(__dirname, "../../studio-api/app/posecraft/pose_catalog.json");
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, JSON.stringify(buildCatalogExport(), null, 1) + "\n", "utf8");
console.log(`Wrote ${POSE_CATALOG.length} poses to ${target}`);
