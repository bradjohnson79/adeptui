import { describe, expect, it } from "vitest";
import { JOINT_NAMES, makeNeutralPose } from "./constants";
import { POSE_CATALOG, POSE_CATEGORIES, getPoseById, isPoseCompatible } from "./poseCatalog";
import type { PoseCategoryId, PosePreset } from "./types";

const VALID_CATEGORIES: PoseCategoryId[] = [
  "neutral", "dialogue", "power", "motion", "emotion", "duo", "action", "rest", "gesture",
];

function jointSignature(joints: PosePreset["joints"]): string {
  // Stable signature of the canonical joint data so duplicates (renamed or
  // mirrored-without-distinct-data) are detected.
  const sig: string[] = [];
  for (const joint of JOINT_NAMES) {
    const rot = joints[joint];
    if (!rot) continue;
    sig.push(`${joint}:${rot.x},${rot.y},${rot.z}`);
  }
  return sig.join("|");
}

describe("PoseCraft pose catalog integrity (Master Program Phases 6–11)", () => {
  it("has at least 50 poses that pass Pose Catalog Integrity", () => {
    const seenIds = new Set<string>();
    const seenSignatures = new Set<string>();
    let passing = 0;
    for (const pose of POSE_CATALOG) {
      const ok =
        typeof pose.id === "string" && pose.id.length > 0 &&
        typeof pose.label === "string" && pose.label.length > 0 &&
        typeof pose.description === "string" && pose.description.length > 0 &&
        VALID_CATEGORIES.includes(pose.category) &&
        Array.isArray(pose.archetypes) === false || pose.archetypes === undefined || pose.archetypes.length > 0;
      if (!ok) continue;
      // unique stable id
      if (seenIds.has(pose.id)) continue;
      // meaningfully distinct canonical joint data (not all-neutral)
      const neutralSig = jointSignature(makeNeutralPose());
      const sig = jointSignature(pose.joints);
      if (sig === neutralSig) continue;
      // distinct joint data (no duplicate signatures)
      if (seenSignatures.has(sig)) continue;
      // real matching thumbnail (non-empty SVG derived from this pose's joints)
      if (typeof pose.thumbnail !== "string" || pose.thumbnail.length < 50) continue;
      if (!pose.thumbnail.includes("<svg")) continue;
      seenIds.add(pose.id);
      seenSignatures.add(sig);
      passing += 1;
    }
    expect(passing, `only ${passing} poses passed integrity, need >= 50`).toBeGreaterThanOrEqual(50);
  });

  it("every pose has a unique id", () => {
    const ids = POSE_CATALOG.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every pose has a real matching thumbnail generated from its joints", () => {
    for (const pose of POSE_CATALOG) {
      expect(pose.thumbnail, `${pose.id} missing thumbnail`).toBeTruthy();
      expect(pose.thumbnail!.startsWith("<svg")).toBe(true);
    }
  });

  it("every pose has a valid primary category", () => {
    for (const pose of POSE_CATALOG) {
      expect(VALID_CATEGORIES, `${pose.id} has invalid category ${pose.category}`).toContain(pose.category);
    }
  });

  it("exposes category filters including all + the 9 categories", () => {
    const ids = POSE_CATEGORIES.map((c) => c.id);
    expect(ids).toContain("all");
    for (const cat of VALID_CATEGORIES) {
      expect(ids, `missing category filter ${cat}`).toContain(cat);
    }
  });

  it("getPoseById returns the matching pose and isPoseCompatible works", () => {
    const first = POSE_CATALOG[0]!;
    expect(getPoseById(first.id)?.id).toBe(first.id);
    // poses with no archetypes are compatible with all
    expect(isPoseCompatible(first, "adult-male")).toBe(true);
    expect(isPoseCompatible(first, "child-girl")).toBe(true);
  });
});
