/**
 * PoseCraft v4 rest-joint bind data.
 *
 * Fable region translations are figure-root space (T-pose, arms along ±X).
 * The certified PoseCraft pose semantics (pose catalog, saved scenes, Pose
 * Intelligence solve_joints) are authored against a HANGING-ARM rest where
 * zero pose = arms at the sides. Per V4 PIVOT BINDING LAW the semantic rig
 * therefore keeps the hanging-arm rest (torso/head/leg pivots taken from the
 * Fable authored pivots, arm segment lengths measured from the Fable T-pose
 * pivots but hung along −Y), and each T-pose arm-chain region mesh receives a
 * static BIND ROTATION (±90° about Z) that maps its authored geometry onto
 * the hanging skeleton. Pose Euler math is unchanged from the certified rig.
 */
import type { ArchetypeId, JointName } from "./types";
import { BODY_REGIONS, REGION_TO_JOINT, type BodyRegion } from "./humanMeshBuilder";

export const V4_PIVOT_TOLERANCE_M = 0.01;

export type Vec3M = { x: number; y: number; z: number };

export const JOINT_PARENT: Record<JointName, JointName | null> = {
  pelvis: null,
  spine: "pelvis",
  chest: "spine",
  neck: "chest",
  head: "neck",
  leftShoulder: "chest",
  leftElbow: "leftShoulder",
  leftWrist: "leftElbow",
  rightShoulder: "chest",
  rightElbow: "rightShoulder",
  rightWrist: "rightElbow",
  leftHip: "pelvis",
  leftKnee: "leftHip",
  leftAnkle: "leftKnee",
  rightHip: "pelvis",
  rightKnee: "rightHip",
  rightAnkle: "rightKnee",
};

/** Measured from the approved quarantine GLB node translations (Figure-root space). */
export const V4_FABLE_ROOT_PIVOTS: Record<ArchetypeId, Record<BodyRegion, Vec3M>> = {
  "adult-male": {
    head: { x: 0, y: 1.621408, z: 0 },
    neck: { x: 0, y: 1.546336, z: 0 },
    chest: { x: 0, y: 1.359348, z: 0 },
    spine: { x: 0, y: 1.160674, z: 0 },
    pelvis: { x: 0, y: 0.962, z: 0 },
    leftUpperArm: { x: -0.24, y: 1.475281, z: 0 },
    leftLowerArm: { x: -0.55, y: 1.475281, z: 0 },
    leftHand: { x: -0.84, y: 1.475281, z: 0 },
    rightUpperArm: { x: 0.24, y: 1.475281, z: 0 },
    rightLowerArm: { x: 0.55, y: 1.475281, z: 0 },
    rightHand: { x: 0.84, y: 1.475281, z: 0 },
    leftUpperLeg: { x: -0.13, y: 0.962, z: 0 },
    leftLowerLeg: { x: -0.13, y: 0.502, z: 0 },
    leftFoot: { x: -0.13, y: 0.052, z: 0 },
    rightUpperLeg: { x: 0.13, y: 0.962, z: 0 },
    rightLowerLeg: { x: 0.13, y: 0.502, z: 0 },
    rightFoot: { x: 0.13, y: 0.052, z: 0 },
  },
  "adult-female": {
    head: { x: 0, y: 1.50416, z: 0 },
    neck: { x: 0, y: 1.43769, z: 0 },
    chest: { x: 0, y: 1.265003, z: 0 },
    spine: { x: 0, y: 1.081523, z: 0 },
    pelvis: { x: 0, y: 0.898043, z: 0 },
    leftUpperArm: { x: -0.17, y: 1.372069, z: 0 },
    leftLowerArm: { x: -0.44, y: 1.372069, z: 0 },
    leftHand: { x: -0.69, y: 1.372069, z: 0 },
    rightUpperArm: { x: 0.17, y: 1.372069, z: 0 },
    rightLowerArm: { x: 0.44, y: 1.372069, z: 0 },
    rightHand: { x: 0.69, y: 1.372069, z: 0 },
    leftUpperLeg: { x: -0.16, y: 0.898043, z: 0 },
    leftLowerLeg: { x: -0.16, y: 0.468043, z: 0 },
    leftFoot: { x: -0.16, y: 0.048043, z: 0 },
    rightUpperLeg: { x: 0.16, y: 0.898043, z: 0 },
    rightLowerLeg: { x: 0.16, y: 0.468043, z: 0 },
    rightFoot: { x: 0.16, y: 0.048043, z: 0 },
  },
  "child-boy": {
    head: { x: 0, y: 1.07646, z: 0 },
    neck: { x: 0, y: 1.018116, z: 0 },
    chest: { x: 0, y: 0.894116, z: 0 },
    spine: { x: 0, y: 0.762366, z: 0 },
    pelvis: { x: 0, y: 0.630615, z: 0 },
    leftUpperArm: { x: -0.145, y: 0.970996, z: 0 },
    leftLowerArm: { x: -0.355, y: 0.970996, z: 0 },
    leftHand: { x: -0.555, y: 0.970996, z: 0 },
    rightUpperArm: { x: 0.145, y: 0.970996, z: 0 },
    rightLowerArm: { x: 0.355, y: 0.970996, z: 0 },
    rightHand: { x: 0.555, y: 0.970996, z: 0 },
    leftUpperLeg: { x: -0.1, y: 0.630615, z: 0 },
    leftLowerLeg: { x: -0.1, y: 0.330615, z: 0 },
    leftFoot: { x: -0.1, y: 0.040615, z: 0 },
    rightUpperLeg: { x: 0.1, y: 0.630615, z: 0 },
    rightLowerLeg: { x: 0.1, y: 0.330615, z: 0 },
    rightFoot: { x: 0.1, y: 0.040615, z: 0 },
  },
  "child-girl": {
    head: { x: 0, y: 1.03808, z: 0 },
    neck: { x: 0, y: 0.98368, z: 0 },
    chest: { x: 0, y: 0.863905, z: 0 },
    spine: { x: 0, y: 0.736645, z: 0 },
    pelvis: { x: 0, y: 0.609385, z: 0 },
    leftUpperArm: { x: -0.135, y: 0.938166, z: 0 },
    leftLowerArm: { x: -0.335, y: 0.938166, z: 0 },
    leftHand: { x: -0.525, y: 0.938166, z: 0 },
    rightUpperArm: { x: 0.135, y: 0.938166, z: 0 },
    rightLowerArm: { x: 0.335, y: 0.938166, z: 0 },
    rightHand: { x: 0.525, y: 0.938166, z: 0 },
    leftUpperLeg: { x: -0.1, y: 0.609385, z: 0 },
    leftLowerLeg: { x: -0.1, y: 0.319385, z: 0 },
    leftFoot: { x: -0.1, y: 0.039385, z: 0 },
    rightUpperLeg: { x: 0.1, y: 0.609385, z: 0 },
    rightLowerLeg: { x: 0.1, y: 0.319385, z: 0 },
    rightFoot: { x: 0.1, y: 0.039385, z: 0 },
  },
};

/** Parent-relative rest translations derived from Fable figure-root pivots. */
export const V4_REST_LOCAL: Record<ArchetypeId, Record<JointName, Vec3M>> = {
  "adult-male": {
    pelvis: { x: 0, y: 0.962, z: 0 },
    spine: { x: 0, y: 0.198674, z: 0 },
    chest: { x: 0, y: 0.198674, z: 0 },
    neck: { x: 0, y: 0.186988, z: 0 },
    head: { x: 0, y: 0.075072, z: 0 },
    leftShoulder: { x: -0.24, y: 0.115933, z: 0 },
    leftElbow: { x: -0.31, y: 0, z: 0 },
    leftWrist: { x: -0.29, y: 0, z: 0 },
    rightShoulder: { x: 0.24, y: 0.115933, z: 0 },
    rightElbow: { x: 0.31, y: 0, z: 0 },
    rightWrist: { x: 0.29, y: 0, z: 0 },
    leftHip: { x: -0.13, y: 0, z: 0 },
    leftKnee: { x: 0, y: -0.46, z: 0 },
    leftAnkle: { x: 0, y: -0.45, z: 0 },
    rightHip: { x: 0.13, y: 0, z: 0 },
    rightKnee: { x: 0, y: -0.46, z: 0 },
    rightAnkle: { x: 0, y: -0.45, z: 0 },
  },
  "adult-female": {
    pelvis: { x: 0, y: 0.898043, z: 0 },
    spine: { x: 0, y: 0.18348, z: 0 },
    chest: { x: 0, y: 0.18348, z: 0 },
    neck: { x: 0, y: 0.172687, z: 0 },
    head: { x: 0, y: 0.06647, z: 0 },
    leftShoulder: { x: -0.17, y: 0.107066, z: 0 },
    leftElbow: { x: -0.27, y: 0, z: 0 },
    leftWrist: { x: -0.25, y: 0, z: 0 },
    rightShoulder: { x: 0.17, y: 0.107066, z: 0 },
    rightElbow: { x: 0.27, y: 0, z: 0 },
    rightWrist: { x: 0.25, y: 0, z: 0 },
    leftHip: { x: -0.16, y: 0, z: 0 },
    leftKnee: { x: 0, y: -0.43, z: 0 },
    leftAnkle: { x: 0, y: -0.42, z: 0 },
    rightHip: { x: 0.16, y: 0, z: 0 },
    rightKnee: { x: 0, y: -0.43, z: 0 },
    rightAnkle: { x: 0, y: -0.42, z: 0 },
  },
  "child-boy": {
    pelvis: { x: 0, y: 0.630615, z: 0 },
    spine: { x: 0, y: 0.131751, z: 0 },
    chest: { x: 0, y: 0.13175, z: 0 },
    neck: { x: 0, y: 0.124, z: 0 },
    head: { x: 0, y: 0.058344, z: 0 },
    leftShoulder: { x: -0.145, y: 0.07688, z: 0 },
    leftElbow: { x: -0.21, y: 0, z: 0 },
    leftWrist: { x: -0.2, y: 0, z: 0 },
    rightShoulder: { x: 0.145, y: 0.07688, z: 0 },
    rightElbow: { x: 0.21, y: 0, z: 0 },
    rightWrist: { x: 0.2, y: 0, z: 0 },
    leftHip: { x: -0.1, y: 0, z: 0 },
    leftKnee: { x: 0, y: -0.3, z: 0 },
    leftAnkle: { x: 0, y: -0.29, z: 0 },
    rightHip: { x: 0.1, y: 0, z: 0 },
    rightKnee: { x: 0, y: -0.3, z: 0 },
    rightAnkle: { x: 0, y: -0.29, z: 0 },
  },
  "child-girl": {
    pelvis: { x: 0, y: 0.609385, z: 0 },
    spine: { x: 0, y: 0.12726, z: 0 },
    chest: { x: 0, y: 0.12726, z: 0 },
    neck: { x: 0, y: 0.119775, z: 0 },
    head: { x: 0, y: 0.0544, z: 0 },
    leftShoulder: { x: -0.135, y: 0.074261, z: 0 },
    leftElbow: { x: -0.2, y: 0, z: 0 },
    leftWrist: { x: -0.19, y: 0, z: 0 },
    rightShoulder: { x: 0.135, y: 0.074261, z: 0 },
    rightElbow: { x: 0.2, y: 0, z: 0 },
    rightWrist: { x: 0.19, y: 0, z: 0 },
    leftHip: { x: -0.1, y: 0, z: 0 },
    leftKnee: { x: 0, y: -0.29, z: 0 },
    leftAnkle: { x: 0, y: -0.28, z: 0 },
    rightHip: { x: 0.1, y: 0, z: 0 },
    rightKnee: { x: 0, y: -0.29, z: 0 },
    rightAnkle: { x: 0, y: -0.28, z: 0 },
  },
};

export function vec3Dist(a: Vec3M, b: Vec3M): number {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = a.z - b.z;
  return Math.hypot(dx, dy, dz);
}

export function addVec(a: Vec3M, b: Vec3M): Vec3M {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

/** Walk ArchetypeSpec-style hanging-arm rest locals into figure-root space. */
export function specRestRootPositions(input: {
  height: number;
  torsoHeight: number;
  shoulderWidth: number;
  hipWidth: number;
  upperArm: number;
  lowerArm: number;
  upperLeg: number;
  lowerLeg: number;
}): Record<JointName, Vec3M> {
  const hipHeight = input.upperLeg + input.lowerLeg;
  const local: Record<JointName, Vec3M> = {
    pelvis: { x: 0, y: hipHeight, z: 0 },
    spine: { x: 0, y: input.torsoHeight * 0.42, z: 0 },
    chest: { x: 0, y: input.torsoHeight * 0.38, z: 0 },
    neck: { x: 0, y: input.torsoHeight * 0.14, z: 0 },
    head: { x: 0, y: input.height * 0.07 * 0.95, z: 0 },
    leftShoulder: { x: -input.shoulderWidth / 2, y: input.torsoHeight * 0.08, z: 0 },
    leftElbow: { x: 0, y: -input.upperArm, z: 0 },
    leftWrist: { x: 0, y: -input.lowerArm, z: 0 },
    rightShoulder: { x: input.shoulderWidth / 2, y: input.torsoHeight * 0.08, z: 0 },
    rightElbow: { x: 0, y: -input.upperArm, z: 0 },
    rightWrist: { x: 0, y: -input.lowerArm, z: 0 },
    leftHip: { x: -input.hipWidth / 2, y: 0, z: 0 },
    leftKnee: { x: 0, y: -input.upperLeg, z: 0 },
    leftAnkle: { x: 0, y: -input.lowerLeg, z: 0 },
    rightHip: { x: input.hipWidth / 2, y: 0, z: 0 },
    rightKnee: { x: 0, y: -input.upperLeg, z: 0 },
    rightAnkle: { x: 0, y: -input.lowerLeg, z: 0 },
  };
  const root = {} as Record<JointName, Vec3M>;
  const walk = (joint: JointName): Vec3M => {
    if (root[joint]) return root[joint];
    const parent = JOINT_PARENT[joint];
    root[joint] = parent ? addVec(walk(parent), local[joint]) : local[joint];
    return root[joint];
  };
  (Object.keys(local) as JointName[]).forEach(walk);
  return root;
}

export type PivotDeltaRow = {
  archetypeId: ArchetypeId;
  region: BodyRegion;
  joint: JointName;
  fable: Vec3M;
  specRest: Vec3M;
  deltaM: number;
  withinTolerance: boolean;
  bind: "zero-local" | "correct-rest";
};

export function measureV4PivotDeltas(
  specByArchetype: Record<ArchetypeId, Parameters<typeof specRestRootPositions>[0]>,
): PivotDeltaRow[] {
  const rows: PivotDeltaRow[] = [];
  (Object.keys(V4_FABLE_ROOT_PIVOTS) as ArchetypeId[]).forEach((archetypeId) => {
    const specRoot = specRestRootPositions(specByArchetype[archetypeId]);
    const fable = V4_FABLE_ROOT_PIVOTS[archetypeId];
    for (const region of BODY_REGIONS) {
      const joint = REGION_TO_JOINT[region];
      const deltaM = vec3Dist(fable[region], specRoot[joint]);
      const withinTolerance = deltaM <= V4_PIVOT_TOLERANCE_M;
      rows.push({
        archetypeId,
        region,
        joint,
        fable: fable[region],
        specRest: specRoot[joint],
        deltaM,
        withinTolerance,
        bind: withinTolerance ? "zero-local" : "correct-rest",
      });
    }
  });
  return rows;
}

export function restLocalFromFableRoot(fable: Record<BodyRegion, Vec3M>): Record<JointName, Vec3M> {
  const root: Record<JointName, Vec3M> = {} as Record<JointName, Vec3M>;
  for (const region of BODY_REGIONS) {
    root[REGION_TO_JOINT[region]] = fable[region];
  }
  const local = {} as Record<JointName, Vec3M>;
  (Object.keys(JOINT_PARENT) as JointName[]).forEach((joint) => {
    const parent = JOINT_PARENT[joint];
    const here = root[joint];
    if (!parent) {
      local[joint] = { ...here };
      return;
    }
    const origin = root[parent];
    local[joint] = { x: here.x - origin.x, y: here.y - origin.y, z: here.z - origin.z };
  });
  return local;
}

export function isLoadCurrent(loadToken: number, expectedToken: number, visualState: string): boolean {
  return visualState !== "DISPOSED" && loadToken === expectedToken;
}

// ---------------------------------------------------------------------------
// HANGING-ARM SEMANTIC REST + REGION BIND ROTATIONS
//
// Zero pose must render arms at the sides (the certified pose semantics).
// Torso / head / leg joint locals come straight from the Fable pivots. The
// arm chain keeps the Fable shoulder pivot but hangs elbow/wrist along −Y
// using the Fable-measured segment lengths (|Δx| between T-pose pivots).
// ---------------------------------------------------------------------------

/** Static bind rotation (radians about Z) applied to each cloned v4 region
 * mesh so the authored T-pose geometry lies along the hanging skeleton.
 * Left arm geometry extends toward −X → +90° maps it to −Y (down); the right
 * arm mirrors. All other regions are authored vertical and bind unrotated. */
export const V4_REGION_BIND_ROTATION_Z: Record<BodyRegion, number> = {
  head: 0, neck: 0, chest: 0, spine: 0, pelvis: 0,
  leftUpperArm: Math.PI / 2, leftLowerArm: Math.PI / 2, leftHand: Math.PI / 2,
  rightUpperArm: -Math.PI / 2, rightLowerArm: -Math.PI / 2, rightHand: -Math.PI / 2,
  leftUpperLeg: 0, leftLowerLeg: 0, leftFoot: 0,
  rightUpperLeg: 0, rightLowerLeg: 0, rightFoot: 0,
};

/** Derive hanging-arm parent-relative rest translations from Fable T-pose
 * figure-root pivots: torso/head/legs identical to the authored pivots; the
 * arm chain hangs along −Y with Fable-measured segment lengths. */
export function hangRestLocalFromFableRoot(fable: Record<BodyRegion, Vec3M>): Record<JointName, Vec3M> {
  const tPose = restLocalFromFableRoot(fable);
  const hang: Record<JointName, Vec3M> = { ...tPose };
  const upperArmLeft = Math.abs(fable.leftLowerArm.x - fable.leftUpperArm.x);
  const lowerArmLeft = Math.abs(fable.leftHand.x - fable.leftLowerArm.x);
  const upperArmRight = Math.abs(fable.rightLowerArm.x - fable.rightUpperArm.x);
  const lowerArmRight = Math.abs(fable.rightHand.x - fable.rightLowerArm.x);
  hang.leftElbow = { x: 0, y: -upperArmLeft, z: 0 };
  hang.leftWrist = { x: 0, y: -lowerArmLeft, z: 0 };
  hang.rightElbow = { x: 0, y: -upperArmRight, z: 0 };
  hang.rightWrist = { x: 0, y: -lowerArmRight, z: 0 };
  return hang;
}

/** Hanging-arm rest locals per archetype (the rig binding the v4 meshes). */
export const V4_HANG_REST_LOCAL: Record<ArchetypeId, Record<JointName, Vec3M>> = Object.fromEntries(
  (Object.keys(V4_FABLE_ROOT_PIVOTS) as ArchetypeId[]).map((archetypeId) => [
    archetypeId,
    hangRestLocalFromFableRoot(V4_FABLE_ROOT_PIVOTS[archetypeId]),
  ]),
) as Record<ArchetypeId, Record<JointName, Vec3M>>;
