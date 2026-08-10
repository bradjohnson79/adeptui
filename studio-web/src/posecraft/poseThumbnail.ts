/**
 * PoseCraft thumbnail pipeline — build-time / lazy render of a real matching
 * thumbnail from canonical pose joint data.
 *
 * Each thumbnail is a deterministic 2D stick-figure projection of the 3D
 * pose: the figure's joint hierarchy is forward-kinematic-projected onto a
 * flat plane using the pose's exact joint rotations (in degrees), then drawn
 * as an SVG. Because the thumbnail is computed FROM the pose's canonical
 * joint data, it always matches the pose — renamed duplicates or placeholder
 * images cannot pass this pipeline.
 *
 * This module is used:
 *  - at build time (scripts/build-pose-thumbnails.mjs) to pre-render the
 *    catalog thumbnails into the catalog module, and
 *  - at runtime as a lazy fallback for custom/user poses (no 50 live Babylon
 *    thumbnail scenes — performance friendly).
 */
import { FIGURE_ARCHETYPES } from "./constants";
import type { ArchetypeId, JointName, PoseMap } from "./types";

type Vec3 = { x: number; y: number; z: number };

const DEG = Math.PI / 180;

// Rest-pose (neutral) joint local positions for an adult-male, normalized to
// figure height ~1.84m. Other archetypes scale proportionally.
function restSkeleton(specHeight: number) {
  const scale = specHeight / 1.84;
  const s = (v: number) => v * scale;
  return {
    pelvis: { x: 0, y: s(0.91), z: 0 },
    spine: { x: 0, y: s(0.28), z: 0 },
    chest: { x: 0, y: s(0.25), z: 0 },
    neck: { x: 0, y: s(0.09), z: 0 },
    head: { x: 0, y: s(0.13), z: 0 },
    leftShoulder: { x: s(-0.22), y: s(0.05), z: 0 },
    leftElbow: { x: 0, y: s(-0.31), z: 0 },
    leftWrist: { x: 0, y: s(-0.29), z: 0 },
    rightShoulder: { x: s(0.22), y: s(0.05), z: 0 },
    rightElbow: { x: 0, y: s(-0.31), z: 0 },
    rightWrist: { x: 0, y: s(-0.29), z: 0 },
    leftHip: { x: s(-0.13), y: 0, z: 0 },
    leftKnee: { x: 0, y: s(-0.46), z: 0 },
    leftAnkle: { x: 0, y: s(-0.45), z: 0 },
    rightHip: { x: s(0.13), y: 0, z: 0 },
    rightKnee: { x: 0, y: s(-0.46), z: 0 },
    rightAnkle: { x: 0, y: s(-0.45), z: 0 },
  } as Record<JointName, Vec3>;
}

const BONE_PARENT: Record<JointName, JointName | null> = {
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

const BONE_ORDER: JointName[] = [
  "pelvis", "spine", "chest", "neck", "head",
  "leftShoulder", "leftElbow", "leftWrist",
  "rightShoulder", "rightElbow", "rightWrist",
  "leftHip", "leftKnee", "leftAnkle",
  "rightHip", "rightKnee", "rightAnkle",
];

function rotateY(v: Vec3, deg: number): Vec3 {
  const r = deg * DEG;
  const c = Math.cos(r), s = Math.sin(r);
  return { x: v.x * c + v.z * s, y: v.y, z: -v.x * s + v.z * c };
}
function rotateX(v: Vec3, deg: number): Vec3 {
  const r = deg * DEG;
  const c = Math.cos(r), s = Math.sin(r);
  return { x: v.x, y: v.y * c - v.z * s, z: v.y * s + v.z * c };
}
function rotateZ(v: Vec3, deg: number): Vec3 {
  const r = deg * DEG;
  const c = Math.cos(r), s = Math.sin(r);
  return { x: v.x * c - v.y * s, y: v.x * s + v.y * c, z: v.z };
}
function add(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

/**
 * Project the figure's posed skeleton to 2D screen points (x right, y down).
 * Camera looks down -Z (front view). Returns absolute joint positions.
 */
function projectSkeleton(pose: PoseMap, archetypeId: ArchetypeId): Record<JointName, Vec3> {
  const spec = FIGURE_ARCHETYPES.find((a) => a.id === archetypeId) ?? FIGURE_ARCHETYPES[0];
  const rest = restSkeleton(spec.height);
  const world: Record<JointName, Vec3> = {} as Record<JointName, Vec3>;
  for (const joint of BONE_ORDER) {
    const parent = BONE_PARENT[joint];
    const localRest = rest[joint];
    const rot = pose[joint] ?? { x: 0, y: 0, z: 0 };
    // Apply local rotation (XYZ) to the rest offset, then translate by parent.
    let offset = localRest;
    offset = rotateX(offset, rot.x);
    offset = rotateY(offset, rot.y);
    offset = rotateZ(offset, rot.z);
    const parentWorld = parent ? world[parent] : { x: 0, y: 0, z: 0 };
    world[joint] = add(parentWorld, offset);
  }
  return world;
}

const LIMB_SEGMENTS: [JointName, JointName][] = [
  ["pelvis", "spine"],
  ["spine", "chest"],
  ["chest", "neck"],
  ["neck", "head"],
  ["chest", "leftShoulder"],
  ["leftShoulder", "leftElbow"],
  ["leftElbow", "leftWrist"],
  ["chest", "rightShoulder"],
  ["rightShoulder", "rightElbow"],
  ["rightElbow", "rightWrist"],
  ["pelvis", "leftHip"],
  ["leftHip", "leftKnee"],
  ["leftKnee", "leftAnkle"],
  ["pelvis", "rightHip"],
  ["rightHip", "rightKnee"],
  ["rightKnee", "rightAnkle"],
];

/**
 * Render a real matching SVG thumbnail for a pose. The thumbnail is a 2D
 * front-projection stick figure derived from the pose's exact joint data.
 */
export function renderPoseThumbnailSvg(
  pose: PoseMap,
  options: { archetypeId?: ArchetypeId; color?: string; size?: number } = {},
): string {
  const archetypeId = options.archetypeId ?? "adult-male";
  const color = options.color ?? "#0f766e";
  const size = options.size ?? 96;
  const world = projectSkeleton(pose, archetypeId);
  // Project to 2D: x -> screen x, y -> screen y (height up), ignore z (front view).
  // Find bounds.
  let minY = Infinity, maxY = -Infinity, minX = Infinity, maxX = -Infinity;
  for (const j of BONE_ORDER) {
    const p = world[j];
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  const pad = 0.12;
  const w = maxX - minX || 1;
  const h = maxY - minY || 1;
  const span = Math.max(w, h) * (1 + pad);
  const ox = (minX + maxX) / 2;
  const oy = (minY + maxY) / 2;
  const toX = (x: number) => ((x - ox) / span + 0.5) * size;
  const toY = (y: number) => (0.5 - (y - oy) / span) * size;
  const r = Math.max(2, size * 0.05);
  let segments = "";
  for (const [a, b] of LIMB_SEGMENTS) {
    const pa = world[a];
    const pb = world[b];
    segments += `<line x1="${toX(pa.x).toFixed(1)}" y1="${toY(pa.y).toFixed(1)}" x2="${toX(pb.x).toFixed(1)}" y2="${toY(pb.y).toFixed(1)}" stroke="${color}" stroke-width="${(size * 0.045).toFixed(1)}" stroke-linecap="round"/>`;
  }
  // Head circle
  const head = world.head;
  const headR = size * 0.07;
  segments += `<circle cx="${toX(head.x).toFixed(1)}" cy="${toY(head.y).toFixed(1)}" r="${headR.toFixed(1)}" fill="${color}"/>`;
  // Joint dots
  for (const j of BONE_ORDER) {
    if (j === "head") continue;
    const p = world[j];
    segments += `<circle cx="${toX(p.x).toFixed(1)}" cy="${toY(p.y).toFixed(1)}" r="${r.toFixed(1)}" fill="${color}" opacity="0.85"/>`;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="${(size*0.12).toFixed(1)}" fill="#eef2f5"/>${segments}</svg>`;
}
