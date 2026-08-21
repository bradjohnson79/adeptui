import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { JOINT_LIMITS } from "./constants";
import { POSE_CATALOG } from "./poseCatalog";

/**
 * Drift guard for the server-side pose catalog mirror.
 *
 * `posecraft.apply_pose` (studio-api) resolves presets from
 * studio-api/app/posecraft/pose_catalog.json. That file is generated from
 * POSE_CATALOG by scripts/export-pose-catalog.ts. If the TS catalog changes
 * without regenerating the export, Co-Director would apply stale joint data —
 * this test fails the build instead.
 */
describe("pose catalog server export", () => {
  const exportPath = resolve(__dirname, "../../../studio-api/app/posecraft/pose_catalog.json");

  it("matches POSE_CATALOG exactly (regenerate with: npx vite-node scripts/export-pose-catalog.ts)", () => {
    const exported = JSON.parse(readFileSync(exportPath, "utf8"));
    expect(exported.schema).toBe("posecraft-pose-catalog@1");
    expect(exported.jointLimits).toEqual(JOINT_LIMITS);
    expect(exported.poses).toHaveLength(POSE_CATALOG.length);
    for (const pose of POSE_CATALOG) {
      const mirrored = exported.poses.find((p: { id: string }) => p.id === pose.id);
      expect(mirrored, `pose ${pose.id} missing from server export`).toBeTruthy();
      expect(mirrored.label).toBe(pose.label);
      expect(mirrored.joints).toEqual(pose.joints);
      expect(mirrored.archetypes ?? null).toEqual(pose.archetypes ?? null);
    }
  });
});
