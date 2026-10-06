import type { PoseCategoryId } from "./types";

export type CreatorPoseGroup =
  | "Standing"
  | "Walking"
  | "Running"
  | "Sitting"
  | "Kneeling"
  | "Crouching"
  | "Lying Down"
  | "Leaning"
  | "Reaching"
  | "Pointing"
  | "Looking"
  | "Custom";

const GROUP_BY_POSE_ID: Record<string, CreatorPoseGroup> = {
  "neutral-hero": "Standing",
  "neutral-idle": "Standing",
  "neutral-relaxed": "Standing",
  "neutral-attention": "Standing",
  "neutral-at-ease": "Standing",
  "neutral-parade-rest": "Standing",
  "motion-walk": "Walking",
  "motion-walk-cycle": "Walking",
  "motion-step-aside": "Walking",
  "motion-run": "Running",
  "rest-seated": "Sitting",
  "motion-perch-sit": "Sitting",
  "motion-kneel": "Kneeling",
  "rest-slumped": "Crouching",
  "rest-reclined": "Lying Down",
  "rest-leaning": "Leaning",
  "action-reach-out": "Reaching",
  "action-reach-up": "Reaching",
  "duo-point-partner": "Pointing",
  "dialogue-listen": "Looking",
  "dialogue-talk": "Looking",
};

export function creatorGroupForPose(poseId: string, category: PoseCategoryId): CreatorPoseGroup {
  if (GROUP_BY_POSE_ID[poseId]) return GROUP_BY_POSE_ID[poseId];
  if (category === "custom") return "Custom";
  if (category === "rest") return "Sitting";
  if (category === "motion") return "Walking";
  return "Standing";
}

export const WALK_FRAMES = [
  { id: "motion-walk", label: "Walk — Left Step" },
  { id: "motion-walk-cycle", label: "Walk — Neutral Passing" },
  { id: "motion-step-aside", label: "Walk — Right Step" },
] as const;

export const LIE_POSES = [
  { id: "rest-reclined", label: "Lie on back" },
] as const;
