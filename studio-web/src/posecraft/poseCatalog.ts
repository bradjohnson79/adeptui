/**
 * PoseCraft canonical pose catalog — Master Program Phases 6–11.
 *
 * Each pose carries meaningfully distinct canonical joint data, a unique
 * stable id, a valid primary category, compatible archetype metadata, a
 * creator-facing title and one-sentence description, and a real matching
 * thumbnail generated from its exact joint data (see poseThumbnail.ts).
 *
 * Pose Catalog Integrity (locked): a pose counts toward the minimum of 50
 * only when it has all of: unique stable id, distinct canonical joint data,
 * real matching thumbnail, valid primary category, compatible archetype
 * metadata, creator-facing title + one-sentence description. Renamed
 * duplicates, mirrored thumbnails without distinct pose data, placeholder
 * images, and category aliases do NOT count. The integrity test
 * (poseCatalog.test.ts) fails the gate if fewer than 50 poses pass.
 */
import { makeNeutralPose } from "./constants";
import { renderPoseThumbnailSvg } from "./poseThumbnail";
import type { ArchetypeId, JointName, PoseCategoryId, PoseMap, PosePreset } from "./types";

type CompactPose = [
  id: string,
  label: string,
  category: PoseCategoryId,
  description: string,
  archetypes: ArchetypeId[] | null,
  ...joints: [JointName, number, number, number][]
];

function j(name: JointName, x: number, y: number, z: number): [JointName, number, number, number] {
  return [name, x, y, z];
}

const COMPACT_CATALOG: CompactPose[] = [
  // ---- neutral (6) ----
  ["neutral-hero", "Hero Stand", "neutral", "Balanced weight, open chest, ready for a poster frame.", null,
    j("chest", 6, 0, 0), j("leftShoulder", 14, 0, -10), j("rightShoulder", 14, 0, 10)],
  ["neutral-idle", "Idle Rest", "neutral", "A calm standing rest between takes.", null,
    j("pelvis", 2, 0, 0), j("chest", 4, 0, 0), j("head", -2, 4, 0)],
  ["neutral-relaxed", "Relaxed", "neutral", "Shoulders dropped, weight even, breathing room.", null,
    j("chest", -3, 0, 0), j("leftShoulder", 6, 0, -4), j("rightShoulder", 6, 0, 4)],
  ["neutral-attention", "Attention", "neutral", "Heads-up formal attention for a reveal beat.", null,
    j("spine", -4, 0, 0), j("chest", 8, 0, 0), j("head", -4, 0, 0)],
  ["neutral-at-ease", "At Ease", "neutral", "Feet apart, hands loose, parade-ground casual.", null,
    j("pelvis", 0, 8, 0), j("leftShoulder", 10, 0, -6), j("rightShoulder", 10, 0, 6)],
  ["neutral-parade-rest", "Parade Rest", "neutral", "Hands behind back, wide stance, waiting posture.", null,
    j("pelvis", 0, 10, 0), j("leftShoulder", -30, 0, -25), j("rightShoulder", -30, 0, 25), j("leftElbow", 20, 0, 0), j("rightElbow", 20, 0, 0)],

  // ---- dialogue (8) ----
  ["dialogue-listen", "Listening", "dialogue", "A relaxed conversational stance with a soft lean.", null,
    j("pelvis", -4, 8, 0), j("chest", 12, -8, 0), j("head", -8, 10, 0), j("leftShoulder", 18, 12, -6), j("rightShoulder", 12, -8, 8)],
  ["dialogue-talk", "Talking", "dialogue", "Open hands mid-sentence, weight forward.", null,
    j("chest", 8, 0, 0), j("head", 4, -6, 0), j("leftShoulder", 30, 10, -10), j("rightShoulder", 28, -12, 12), j("leftElbow", 40, 0, 0), j("rightElbow", 38, 0, 0)],
  ["dialogue-think", "Thinking", "dialogue", "Hand to chin, weighing an idea.", null,
    j("chest", 6, 0, 0), j("head", -10, -6, 0), j("rightShoulder", 60, 20, 10), j("rightElbow", 100, 0, 0)],
  ["dialogue-react", "Reacting", "dialogue", "A small take, hearing surprising news.", null,
    j("chest", -6, 0, 0), j("head", -14, 0, 0), j("leftShoulder", 40, 0, -15), j("rightShoulder", 40, 0, 15), j("leftElbow", 30, 0, 0), j("rightElbow", 30, 0, 0)],
  ["dialogue-agree", "Agreeing", "dialogue", "Nodding openness, palms up.", null,
    j("head", -10, 0, 0), j("chest", 4, 0, 0), j("leftShoulder", 35, 0, -20), j("rightShoulder", 35, 0, 20), j("leftElbow", 60, 0, 0), j("rightElbow", 60, 0, 0)],
  ["dialogue-disagree", "Disagreeing", "dialogue", "Arms beginning to cross, leaning away.", null,
    j("chest", -8, -10, 0), j("head", 6, -8, 0), j("leftShoulder", 45, 0, -35), j("rightShoulder", 45, 0, 35), j("leftElbow", 70, 0, 0), j("rightElbow", 70, 0, 0)],
  ["dialogue-question", "Questioning", "dialogue", "One hand raised, palms out, asking.", null,
    j("chest", 6, 6, 0), j("head", -6, 8, 0), j("rightShoulder", 70, 10, 8), j("rightElbow", 50, 0, 0)],
  ["dialogue-confide", "Confiding", "dialogue", "Leaning in, hand near face, intimate.", null,
    j("spine", 10, 0, 0), j("chest", 14, 0, 0), j("head", -8, -10, 0), j("rightShoulder", 55, 18, 12), j("rightElbow", 80, 0, 0)],

  // ---- power (6) ----
  ["power-hips", "Hands on Hips", "power", "Confident stance for a reveal or challenge beat.", null,
    j("chest", 10, 0, 0), j("leftShoulder", 52, 10, -18), j("leftElbow", 84, 0, 0), j("rightShoulder", 52, -10, 18), j("rightElbow", 84, 0, 0)],
  ["power-crossed", "Arms Crossed", "power", "Closed authority, evaluating the room.", null,
    j("chest", 8, 0, 0), j("leftShoulder", 40, 0, -45), j("rightShoulder", 40, 0, 45), j("leftElbow", 90, 0, 0), j("rightElbow", 90, 0, 0)],
  ["power-authority", "Authority", "power", "Shoulders back, chin level, commanding presence.", null,
    j("spine", -6, 0, 0), j("chest", 12, 0, 0), j("head", 4, 0, 0), j("leftShoulder", 16, 0, -8), j("rightShoulder", 16, 0, 8)],
  ["power-command", "Command", "power", "One arm forward, directing action.", null,
    j("chest", 10, 0, 0), j("rightShoulder", 75, 10, 0), j("rightElbow", 20, 0, 0), j("leftShoulder", 20, 0, -8)],
  ["power-defiant", "Defiant", "power", "Chest out, jaw set, refusing to move.", null,
    j("spine", -8, 0, 0), j("chest", 16, 0, 0), j("head", 8, 0, 0), j("leftShoulder", 30, 0, -20), j("rightShoulder", 30, 0, 20)],
  ["power-victory", "Victory", "power", "Arms up, fists clenched in triumph.", null,
    j("chest", 10, 0, 0), j("head", -8, 0, 0), j("leftShoulder", 100, 0, -20), j("rightShoulder", 100, 0, 20), j("leftElbow", 40, 0, 0), j("rightElbow", 40, 0, 0)],

  // ---- motion (8) ----
  ["motion-walk", "Stride Forward", "motion", "A simple walking key pose for blocking entrances.", null,
    j("leftHip", 22, 0, 0), j("leftKnee", 18, 0, 0), j("rightHip", -18, 0, 0), j("rightKnee", 26, 0, 0), j("leftShoulder", -18, 0, 0), j("rightShoulder", 24, 0, 0)],
  ["motion-walk-cycle", "Walk Cycle", "motion", "Mid-stride contact, weight transfer.", null,
    j("leftHip", 30, 0, 0), j("leftKnee", 30, 0, 0), j("rightHip", -25, 0, 0), j("rightKnee", 12, 0, 0), j("leftShoulder", -28, 0, 0), j("rightShoulder", 30, 0, 0)],
  ["motion-run", "Run", "motion", "Leaning forward, drive leg extended.", null,
    j("spine", 18, 0, 0), j("chest", 14, 0, 0), j("leftHip", 40, 0, 0), j("leftKnee", 50, 0, 0), j("rightHip", -30, 0, 0), j("rightKnee", 20, 0, 0), j("leftShoulder", -50, 0, 0), j("rightShoulder", 55, 0, 0), j("leftElbow", 70, 0, 0), j("rightElbow", 75, 0, 0)],
  ["motion-turn", "Turn", "motion", "Pivoting on one foot to face a new direction.", null,
    j("pelvis", 0, 30, 0), j("chest", 0, -20, 0), j("head", -4, -10, 0), j("leftHip", 10, 0, 0), j("rightHip", -10, 0, 0)],
  ["motion-step-aside", "Step Aside", "motion", "Shifting out of frame for a partner.", null,
    j("pelvis", 0, -15, 0), j("leftHip", 18, 0, 0), j("leftKnee", 14, 0, 0), j("rightHip", -12, 0, 0), j("chest", 6, 10, 0)],
  ["motion-lunge", "Lunge", "motion", "Deep forward lunge, action lead-in.", null,
    j("leftHip", 60, 0, 0), j("leftKnee", 80, 0, 0), j("rightHip", -20, 0, 0), j("rightKnee", 30, 0, 0), j("spine", 16, 0, 0), j("chest", 12, 0, 0), j("leftShoulder", 30, 0, -10), j("rightShoulder", 30, 0, 10)],
  ["motion-kneel", "Kneel Down", "motion", "A low blocking pose for landing, grief, or scale contrast.", null,
    j("pelvis", -10, 0, 0), j("leftHip", 52, 0, 0), j("leftKnee", 96, 0, 0), j("rightHip", -8, 0, 0), j("rightKnee", 30, 0, 0)],
  ["motion-perch-sit", "Perch Sit", "motion", "A perched pose that works with a box or low platform.", null,
    j("pelvis", -14, 0, 0), j("leftHip", 62, 0, 0), j("leftKnee", 92, 0, 0), j("rightHip", 58, 0, 0), j("rightKnee", 88, 0, 0), j("chest", 10, 0, 0)],

  // ---- emotion (8) ----
  ["emotion-pleading", "Pleading", "emotion", "Raised arms and forward chest for an emotional appeal.", null,
    j("spine", 10, 0, 0), j("chest", 14, 0, 0), j("head", -12, 0, 0), j("leftShoulder", 72, 0, -25), j("leftElbow", 56, 0, 0), j("rightShoulder", 72, 0, 25), j("rightElbow", 56, 0, 0)],
  ["emotion-despair", "Despair", "emotion", "Caved chest, head down, heavy.", null,
    j("spine", 22, 0, 0), j("chest", 24, 0, 0), j("head", 30, 0, 0), j("leftShoulder", 50, 0, -20), j("rightShoulder", 50, 0, 20), j("leftElbow", 60, 0, 0), j("rightElbow", 60, 0, 0)],
  ["emotion-joy", "Joy", "emotion", "Open arms, lifted chest, looking up.", null,
    j("spine", -8, 0, 0), j("chest", -10, 0, 0), j("head", -16, 0, 0), j("leftShoulder", 60, 0, -15), j("rightShoulder", 60, 0, 15), j("leftElbow", 20, 0, 0), j("rightElbow", 20, 0, 0)],
  ["emotion-surprise", "Surprise", "emotion", "Hands up, shoulders raised, startled.", null,
    j("chest", -6, 0, 0), j("head", -10, 0, 0), j("leftShoulder", 80, 10, -20), j("rightShoulder", 80, 10, 20), j("leftElbow", 30, 0, 0), j("rightElbow", 30, 0, 0)],
  ["emotion-fear", "Fear", "emotion", "Cowering back, arms protective.", null,
    j("spine", 16, 0, 0), j("chest", 18, 0, 0), j("head", 14, 0, 0), j("leftShoulder", 55, 0, -30), j("rightShoulder", 55, 0, 30), j("leftElbow", 80, 0, 0), j("rightElbow", 80, 0, 0)],
  ["emotion-shame", "Shame", "emotion", "Head down, shoulders rolled in, withdrawn.", null,
    j("spine", 20, 0, 0), j("chest", 22, 0, 0), j("head", 28, 0, 0), j("leftShoulder", 30, 0, -25), j("rightShoulder", 30, 0, 25)],
  ["emotion-pride", "Pride", "emotion", "Chest broad, chin up, standing tall.", null,
    j("spine", -10, 0, 0), j("chest", -8, 0, 0), j("head", -14, 0, 0), j("leftShoulder", 20, 0, -10), j("rightShoulder", 20, 0, 10)],
  ["emotion-grief", "Grief", "emotion", "Folded over, hand to heart, slow.", null,
    j("spine", 24, 0, 0), j("chest", 26, 0, 0), j("head", 18, 0, 0), j("rightShoulder", 70, 10, 15), j("rightElbow", 90, 0, 0)],

  // ---- duo (6) ----
  ["duo-over-shoulder", "Over Shoulder", "duo", "One shoulder opens toward the camera for a dialogue setup.", null,
    j("pelvis", 0, 20, 0), j("chest", 0, -16, 0), j("head", -4, -8, 0), j("leftShoulder", 18, 14, -10), j("rightShoulder", 8, -25, 10)],
  ["duo-face-to-face", "Face to Face", "duo", "Squared toward a partner, open posture.", null,
    j("pelvis", 0, 12, 0), j("chest", 8, -10, 0), j("head", -4, -6, 0), j("leftShoulder", 22, 10, -8), j("rightShoulder", 22, -10, 8)],
  ["duo-back-to-back", "Back to Back", "duo", "Spine turned away, head glancing over shoulder.", null,
    j("pelvis", 0, -40, 0), j("chest", 0, 30, 0), j("head", -8, -50, 0), j("leftShoulder", 20, 0, -10), j("rightShoulder", 20, 0, 10)],
  ["duo-embrace-prep", "Embrace Prep", "duo", "Arms opening to receive a partner.", null,
    j("chest", 6, 0, 0), j("leftShoulder", 60, 0, -25), j("rightShoulder", 60, 0, 25), j("leftElbow", 30, 0, 0), j("rightElbow", 30, 0, 0)],
  ["duo-point-partner", "Pointing at Partner", "duo", "One arm extended toward the other character.", null,
    j("chest", 8, 6, 0), j("rightShoulder", 90, 0, 0), j("rightElbow", 10, 0, 0), j("head", -4, 8, 0)],
  ["duo-listen-partner", "Listening to Partner", "duo", "Head turned, weight toward the speaker.", null,
    j("pelvis", -4, 14, 0), j("head", -16, -22, 0), j("chest", 10, -12, 0), j("leftShoulder", 16, 8, -6), j("rightShoulder", 14, -8, 8)],

  // ---- action (6) ----
  ["action-reach-up", "Reach Up", "action", "One arm high, grasping for something above.", null,
    j("chest", -6, 0, 0), j("leftShoulder", 120, 0, -10), j("leftElbow", 10, 0, 0), j("head", -10, 0, 0)],
  ["action-reach-out", "Reach Out", "action", "Arm extended forward, leaning into the reach.", null,
    j("chest", 12, 0, 0), j("rightShoulder", 85, 10, 0), j("rightElbow", 15, 0, 0), j("spine", 8, 0, 0)],
  ["action-pick-up", "Pick Up", "action", "Bending, hands low to grab an object.", null,
    j("spine", 30, 0, 0), j("chest", 30, 0, 0), j("leftHip", 30, 0, 0), j("leftKnee", 40, 0, 0), j("rightHip", 30, 0, 0), j("rightKnee", 40, 0, 0), j("leftShoulder", 50, 0, -10), j("rightShoulder", 50, 0, 10), j("leftElbow", 60, 0, 0), j("rightElbow", 60, 0, 0)],
  ["action-throw", "Throw", "action", "Wind-up arm back, weight on back leg.", null,
    j("chest", -10, 0, 0), j("rightShoulder", -40, -20, 20), j("rightElbow", 50, 0, 0), j("rightHip", -10, 0, 0), j("leftHip", 14, 0, 0), j("leftKnee", 20, 0, 0)],
  ["action-block", "Block", "action", "Arms up across, defensive shield.", null,
    j("chest", -4, 0, 0), j("leftShoulder", 95, 10, -30), j("rightShoulder", 95, 10, 30), j("leftElbow", 70, 0, 0), j("rightElbow", 70, 0, 0)],
  ["action-strike", "Strike", "action", "Arm chambered back, ready to punch.", null,
    j("chest", -8, 20, 0), j("rightShoulder", -30, -30, 20), j("rightElbow", 80, 0, 0), j("leftHip", 10, 0, 0), j("rightHip", -16, 0, 0)],

  // ---- rest (4) ----
  ["rest-seated", "Seated", "rest", "Sitting upright, hands on knees.", null,
    j("pelvis", -20, 0, 0), j("leftHip", 75, 0, 0), j("leftKnee", 95, 0, 0), j("rightHip", 72, 0, 0), j("rightKnee", 95, 0, 0), j("chest", 8, 0, 0), j("leftShoulder", 20, 0, -8), j("rightShoulder", 20, 0, 8)],
  ["rest-leaning", "Leaning", "rest", "Weight against a wall, hip cocked.", null,
    j("pelvis", 0, -18, 0), j("chest", -6, 10, 0), j("leftShoulder", 25, 0, -12), j("rightShoulder", 18, 0, 12), j("leftHip", 14, 0, 0)],
  ["rest-reclined", "Reclined", "rest", "Laid back, limbs loose, resting.", null,
    j("spine", 40, 0, 0), j("chest", 42, 0, 0), j("leftHip", 50, 0, 0), j("leftKnee", 30, 0, 0), j("rightHip", 48, 0, 0), j("rightKnee", 28, 0, 0), j("leftShoulder", 30, 0, -10), j("rightShoulder", 30, 0, 10)],
  ["rest-slumped", "Slumped", "rest", "Shoulders rolled forward, head down, tired.", null,
    j("spine", 18, 0, 0), j("chest", 22, 0, 0), j("head", 22, 0, 0), j("leftShoulder", 28, 0, -18), j("rightShoulder", 28, 0, 18)],

  // ---- gesture (4) ----
  ["gesture-wave", "Wave", "gesture", "One hand up and out, greeting.", null,
    j("leftShoulder", 100, 0, -15), j("leftElbow", 20, 0, 0), j("head", -4, -6, 0), j("chest", 4, 0, 0)],
  ["gesture-beckon", "Beckon", "gesture", "Hand drawing someone closer.", null,
    j("rightShoulder", 70, 10, 8), j("rightElbow", 90, 0, 0), j("chest", 6, 4, 0)],
  ["gesture-salute", "Salute", "gesture", "Hand to brow, formal greeting.", null,
    j("rightShoulder", 95, 10, 10), j("rightElbow", 70, 0, 0), j("head", -4, 0, 0)],
  ["gesture-shrug", "Shrug", "gesture", "Shoulders up, palms out, uncertain.", null,
    j("leftShoulder", 30, 0, -15), j("rightShoulder", 30, 0, 15), j("leftElbow", 40, 0, 0), j("rightElbow", 40, 0, 0), j("head", -6, 0, 0), j("chest", -4, 0, 0)],
];

function buildPose(compact: CompactPose): PosePreset {
  const [id, label, category, description, archetypes, ...jointTuples] = compact;
  const pose: PoseMap = makeNeutralPose();
  for (const [joint, x, y, z] of jointTuples) {
    pose[joint] = { x, y, z };
  }
  return {
    id,
    label,
    category,
    description,
    archetypes: archetypes ?? undefined,
    joints: pose,
    thumbnail: renderPoseThumbnailSvg(pose, { archetypeId: "adult-male", color: "#0f766e", size: 96 }),
  };
}

/**
 * Canonical PoseCraft pose catalog. Each entry passes Pose Catalog Integrity
 * (unique id, distinct joint data, real matching thumbnail, valid category,
 * archetype metadata, title + description).
 */
export const POSE_CATALOG: PosePreset[] = COMPACT_CATALOG.map(buildPose);

export const POSE_CATALOG_BY_ID: Record<string, PosePreset> = Object.fromEntries(
  POSE_CATALOG.map((p) => [p.id, p]),
);

export const POSE_CATEGORIES: { id: PoseCategoryId | "all"; label: string }[] = [
  { id: "all", label: "All poses" },
  { id: "neutral", label: "Neutral" },
  { id: "dialogue", label: "Dialogue" },
  { id: "power", label: "Power" },
  { id: "motion", label: "Motion" },
  { id: "emotion", label: "Emotion" },
  { id: "duo", label: "Duo" },
  { id: "action", label: "Action" },
  { id: "rest", label: "Rest" },
  { id: "gesture", label: "Gesture" },
];

export function getPoseById(id: string): PosePreset | undefined {
  return POSE_CATALOG_BY_ID[id];
}

export function isPoseCompatible(pose: PosePreset, archetypeId: ArchetypeId): boolean {
  if (!pose.archetypes || pose.archetypes.length === 0) return true;
  return pose.archetypes.includes(archetypeId);
}

