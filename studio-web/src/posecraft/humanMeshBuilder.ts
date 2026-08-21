/**
 * PoseCraft — Faceted anatomical low-poly humans (Revision C Phase 2, v3).
 *
 * Region meshes stay parented to the existing 17-joint TransformNode rig.
 * The builder does not own posing, gizmos, or the pose catalog.
 *
 * Visual target: faceted / diamond-cut anatomy (man, woman, boy, girl),
 * T-pose, unclothed base mesh, 2,000–5,000 triangles, flat-shaded facets.
 */
import {
  Mesh,
  MeshBuilder,
  Scene,
  StandardMaterial,
  TransformNode,
  VertexData,
} from "@babylonjs/core";
import type { ArchetypeId, ArchetypeSpec, JointName } from "./types";

export type BodyRegion =
  | "head" | "neck" | "chest" | "spine" | "pelvis"
  | "leftUpperArm" | "leftLowerArm" | "leftHand"
  | "rightUpperArm" | "rightLowerArm" | "rightHand"
  | "leftUpperLeg" | "leftLowerLeg" | "leftFoot"
  | "rightUpperLeg" | "rightLowerLeg" | "rightFoot";

export const REGION_TO_JOINT: Record<BodyRegion, JointName> = {
  head: "head", neck: "neck", chest: "chest", spine: "spine", pelvis: "pelvis",
  leftUpperArm: "leftShoulder", leftLowerArm: "leftElbow", leftHand: "leftWrist",
  rightUpperArm: "rightShoulder", rightLowerArm: "rightElbow", rightHand: "rightWrist",
  leftUpperLeg: "leftHip", leftLowerLeg: "leftKnee", leftFoot: "leftAnkle",
  rightUpperLeg: "rightHip", rightLowerLeg: "rightKnee", rightFoot: "rightAnkle",
};

export const BODY_REGIONS: BodyRegion[] = Object.keys(REGION_TO_JOINT) as BodyRegion[];

export type HumanMeshMetadata = {
  modelId: string;
  jointCount: number;
  bodyRegions: BodyRegion[];
  legacyBlockModel: false;
  triangleCount?: number;
  gender?: "male" | "female";
  ageClass?: "adult" | "child";
  heightM?: number;
  rig?: string;
  assetSource?: string;
  visualState?: "LOADING" | "READY" | "ERROR" | "DISPOSED";
};

export const HUMAN_MODEL_IDS = {
  "adult-male": "adult-male-lowpoly-v4",
  "adult-female": "adult-female-lowpoly-v4",
  "child-boy": "child-boy-lowpoly-v4",
  "child-girl": "child-girl-lowpoly-v4",
} as const;

export function getHumanModelId(archetypeId: ArchetypeSpec["id"]): string {
  return HUMAN_MODEL_IDS[archetypeId] ?? "adult-male-lowpoly-v4";
}

export function figureIdentity(archetypeId: ArchetypeId): { gender: "male" | "female"; ageClass: "adult" | "child" } {
  if (archetypeId === "adult-female" || archetypeId === "child-girl") return { gender: "female", ageClass: archetypeId === "child-girl" ? "child" : "adult" };
  return { gender: archetypeId === "child-boy" ? "male" : "male", ageClass: archetypeId === "child-boy" ? "child" : "adult" };
}

export function buildHumanMeshMetadata(archetypeId: ArchetypeSpec["id"], triangleCount = 0, heightM = 0): HumanMeshMetadata {
  const id = figureIdentity(archetypeId);
  return {
    modelId: getHumanModelId(archetypeId),
    jointCount: 17,
    bodyRegions: [...BODY_REGIONS],
    legacyBlockModel: false as const,
    triangleCount,
    gender: id.gender,
    ageClass: id.ageClass,
    heightM,
    rig: "posecraft-v2",
  };
}

type JointNodes = Record<JointName, TransformNode>;

function flatShade(mesh: Mesh): Mesh {
  mesh.convertToFlatShadedMesh();
  mesh.receiveShadows = false;
  return mesh;
}

function tagMesh(mesh: Mesh, figureId: string, region: BodyRegion, material: StandardMaterial): Mesh {
  mesh.name = `${figureId}-body-${region}`;
  mesh.material = material;
  mesh.isPickable = true;
  mesh.metadata = { figureId, region, kind: "body" };
  return mesh;
}

export function countMeshTriangles(mesh: Mesh): number {
  const indices = mesh.getIndices();
  return indices ? Math.floor(indices.length / 3) : 0;
}

function applyCustom(
  scene: Scene,
  name: string,
  positions: number[],
  indices: number[],
): Mesh {
  const normals: number[] = [];
  const vertexData = new VertexData();
  vertexData.positions = positions;
  vertexData.indices = indices;
  VertexData.ComputeNormals(positions, indices, normals);
  vertexData.normals = normals;
  const mesh = new Mesh(name, scene);
  vertexData.applyToMesh(mesh);
  return mesh;
}

function ringTorso(
  scene: Scene,
  parent: TransformNode,
  figureId: string,
  region: BodyRegion,
  rings: Array<{ y: number; rx: number; rz: number }>,
  sides: number,
  material: StandardMaterial,
): Mesh {
  const positions: number[] = [];
  const indices: number[] = [];
  for (const ring of rings) {
    for (let i = 0; i < sides; i += 1) {
      const a = (i / sides) * Math.PI * 2;
      positions.push(Math.cos(a) * ring.rx, ring.y, Math.sin(a) * ring.rz);
    }
  }
  for (let r = 0; r < rings.length - 1; r += 1) {
    for (let i = 0; i < sides; i += 1) {
      const a = r * sides + i;
      const b = r * sides + ((i + 1) % sides);
      const c = (r + 1) * sides + i;
      const d = (r + 1) * sides + ((i + 1) % sides);
      indices.push(a, c, b, b, c, d);
    }
  }
  const mesh = applyCustom(scene, `${figureId}-body-${region}`, positions, indices);
  mesh.parent = parent;
  flatShade(mesh);
  tagMesh(mesh, figureId, region, material);
  return mesh;
}

function createFacetedHead(
  scene: Scene, parent: TransformNode, figureId: string, radius: number, material: StandardMaterial,
): Mesh {
  const mesh = MeshBuilder.CreateIcoSphere(`${figureId}-body-head`, { radius, subdivisions: 2 }, scene);
  mesh.parent = parent;
  mesh.position.y = radius * 0.45;
  mesh.scaling.z = 0.92;
  mesh.scaling.x = 0.88;
  flatShade(mesh);
  tagMesh(mesh, figureId, "head", material);
  return mesh;
}

function createNeck(
  scene: Scene, parent: TransformNode, figureId: string,
  options: { height: number; radius: number }, material: StandardMaterial,
): Mesh {
  const mesh = MeshBuilder.CreateCylinder(`${figureId}-body-neck`, {
    height: options.height, diameter: options.radius * 2, tessellation: 12,
  }, scene);
  mesh.parent = parent;
  mesh.position.y = options.height / 2;
  flatShade(mesh);
  tagMesh(mesh, figureId, "neck", material);
  return mesh;
}

function createAnatomicalLimb(
  scene: Scene, parent: TransformNode, figureId: string, region: BodyRegion,
  options: { length: number; top: number; mid: number; bottom: number; y: number },
  material: StandardMaterial,
): Mesh {
  const rings = [
    { y: options.y + options.length / 2, rx: options.top, rz: options.top * 0.92 },
    { y: options.y + options.length * 0.32, rx: options.top * 1.05, rz: options.top * 0.9 },
    { y: options.y + options.length * 0.12, rx: options.mid * 1.02, rz: options.mid * 0.9 },
    { y: options.y, rx: options.mid, rz: options.mid * 0.88 },
    { y: options.y - options.length * 0.16, rx: options.mid * 0.96, rz: options.mid * 0.86 },
    { y: options.y - options.length * 0.34, rx: options.bottom * 1.04, rz: options.bottom * 0.9 },
    { y: options.y - options.length / 2, rx: options.bottom, rz: options.bottom * 0.86 },
  ];
  return ringTorso(scene, parent, figureId, region, rings, 12, material);
}

function createFacetedHand(
  scene: Scene, parent: TransformNode, figureId: string, region: BodyRegion,
  options: { palmW: number; palmH: number; palmD: number; side: 1 | -1 },
  material: StandardMaterial,
): Mesh {
  const palm = ringTorso(scene, parent, figureId, region, [
    { y: 0, rx: options.palmW * 0.48, rz: options.palmD * 0.38 },
    { y: -options.palmH * 0.45, rx: options.palmW * 0.5, rz: options.palmD * 0.42 },
    { y: -options.palmH, rx: options.palmW * 0.46, rz: options.palmD * 0.36 },
  ], 8, material);
  palm.position.z = options.palmD * 0.12;

  const fingerW = options.palmW * 0.2;
  const fingerH = options.palmH * 0.72;
  for (let i = 0; i < 4; i += 1) {
    const finger = MeshBuilder.CreateCylinder(`${figureId}-body-${region}-f${i}`, {
      height: fingerH, diameterTop: fingerW * 0.72, diameterBottom: fingerW * 0.95, tessellation: 6,
    }, scene);
    finger.parent = palm;
    finger.position.x = (i - 1.5) * (options.palmW * 0.22);
    finger.position.y = -options.palmH * 0.55;
    finger.position.z = options.palmD * 0.18;
    flatShade(finger);
    finger.material = material;
    finger.isPickable = true;
    finger.metadata = { figureId, region, kind: "body" };
  }
  const thumb = MeshBuilder.CreateCylinder(`${figureId}-body-${region}-thumb`, {
    height: fingerH * 0.7, diameterTop: fingerW * 0.7, diameterBottom: fingerW * 1.05, tessellation: 6,
  }, scene);
  thumb.parent = palm;
  thumb.position.x = options.side * (options.palmW * 0.52);
  thumb.position.y = -options.palmH * 0.08;
  thumb.position.z = options.palmD * 0.28;
  thumb.rotation.z = options.side * -0.7;
  thumb.rotation.x = 0.35;
  flatShade(thumb);
  thumb.material = material;
  thumb.isPickable = true;
  thumb.metadata = { figureId, region, kind: "body" };
  return palm;
}

function createFacetedFoot(
  scene: Scene, parent: TransformNode, figureId: string, region: BodyRegion,
  options: { width: number; length: number; height: number },
  material: StandardMaterial,
): Mesh {
  const w = options.width;
  const l = options.length;
  const h = options.height;
  const positions = [
    -w / 2, 0, -l * 0.35,
    w / 2, 0, -l * 0.35,
    -w * 0.42, 0, l * 0.55,
    w * 0.42, 0, l * 0.55,
    -w / 2, h, -l * 0.35,
    w / 2, h, -l * 0.35,
    -w * 0.38, h * 0.55, l * 0.2,
    w * 0.38, h * 0.55, l * 0.2,
    0, h * 0.35, l * 0.58,
  ];
  const indices = [
    0, 2, 3, 0, 3, 1,
    4, 5, 7, 4, 7, 6,
    6, 7, 8,
    0, 1, 5, 0, 5, 4,
    2, 8, 3,
    0, 4, 6, 0, 6, 2,
    1, 3, 7, 1, 7, 5,
    2, 6, 8,
    3, 8, 7,
  ];
  const mesh = applyCustom(scene, `${figureId}-body-${region}`, positions, indices);
  mesh.parent = parent;
  mesh.position.y = -h * 0.05;
  mesh.position.z = l * 0.18;
  mesh.material = material;
  mesh.isPickable = true;
  mesh.metadata = { figureId, region, kind: "body" };
  mesh.convertToFlatShadedMesh();
  return mesh;
}

type ProportionTuning = {
  headRadius: number; neckRadius: number; neckLength: number;
  chestTop: number; chestMid: number; chestBot: number; chestH: number;
  waistTop: number; waistMid: number; waistBot: number; waistH: number;
  pelvisTop: number; pelvisMid: number; pelvisBot: number; pelvisH: number;
  chestDepth: number; waistDepth: number; pelvisDepth: number;
  pecBoost: number; hipBoost: number;
  upperArmTop: number; upperArmMid: number; upperArmBot: number;
  lowerArmTop: number; lowerArmMid: number; lowerArmBot: number;
  upperLegTop: number; upperLegMid: number; upperLegBot: number;
  lowerLegTop: number; lowerLegMid: number; lowerLegBot: number;
  handPalmWidth: number; handPalmHeight: number; handPalmDepth: number;
  footWidth: number; footLength: number; footHeight: number;
  deltoid: number;
};

function tuneProportions(spec: ArchetypeSpec): ProportionTuning {
  const h = spec.height;
  const sw = spec.shoulderWidth;
  const hw = spec.hipWidth;
  const lt = spec.limbThickness;
  const isChild = spec.id === "child-boy" || spec.id === "child-girl";
  const headRadius = isChild ? h * 0.11 : h * 0.074;
  const neckRadius = sw * (spec.id === "adult-female" ? 0.14 : 0.16);
  const neckLength = spec.torsoHeight * (isChild ? 0.11 : 0.12);

  let chestTop = sw * 0.52;
  let chestMid = sw * 0.5;
  let chestBot = sw * 0.4;
  let waistTop = sw * 0.36;
  let waistMid = hw * 0.48;
  let waistBot = hw * 0.5;
  let pelvisTop = hw * 0.52;
  let pelvisMid = hw * 0.54;
  let pelvisBot = hw * 0.42;
  let pecBoost = 1;
  let hipBoost = 1;
  let chestDepth = sw * 0.32;
  let waistDepth = sw * 0.28;
  let pelvisDepth = hw * 0.42;

  if (spec.id === "adult-male") {
    chestTop = sw * 0.55; chestMid = sw * 0.5; chestBot = sw * 0.38;
    waistTop = sw * 0.34; waistMid = hw * 0.46; waistBot = hw * 0.5;
    pelvisTop = hw * 0.5; pelvisMid = hw * 0.52; pelvisBot = hw * 0.4;
    pecBoost = 1.12; hipBoost = 0.96;
    chestDepth = sw * 0.34; waistDepth = sw * 0.26; pelvisDepth = hw * 0.4;
  } else if (spec.id === "adult-female") {
    chestTop = sw * 0.5; chestMid = sw * 0.48; chestBot = sw * 0.36;
    waistTop = sw * 0.28; waistMid = sw * 0.3; waistBot = hw * 0.48;
    pelvisTop = hw * 0.56; pelvisMid = hw * 0.6; pelvisBot = hw * 0.46;
    pecBoost = 1.08; hipBoost = 1.12;
    chestDepth = sw * 0.3; waistDepth = sw * 0.24; pelvisDepth = hw * 0.46;
  } else if (spec.id === "child-boy") {
    chestTop = sw * 0.48; chestMid = sw * 0.46; chestBot = sw * 0.42;
    waistTop = sw * 0.4; waistMid = sw * 0.4; waistBot = hw * 0.46;
    pelvisTop = hw * 0.46; pelvisMid = hw * 0.46; pelvisBot = hw * 0.4;
    pecBoost = 1.0; hipBoost = 1.0;
    chestDepth = sw * 0.3; waistDepth = sw * 0.28; pelvisDepth = hw * 0.38;
  } else {
    chestTop = sw * 0.46; chestMid = sw * 0.44; chestBot = sw * 0.38;
    waistTop = sw * 0.36; waistMid = sw * 0.38; waistBot = hw * 0.48;
    pelvisTop = hw * 0.5; pelvisMid = hw * 0.52; pelvisBot = hw * 0.42;
    pecBoost = 1.02; hipBoost = 1.06;
    chestDepth = sw * 0.28; waistDepth = sw * 0.26; pelvisDepth = hw * 0.4;
  }

  return {
    headRadius, neckRadius, neckLength,
    chestTop, chestMid, chestBot, chestH: spec.torsoHeight * 0.4,
    waistTop, waistMid, waistBot, waistH: spec.torsoHeight * 0.24,
    pelvisTop, pelvisMid, pelvisBot, pelvisH: spec.torsoHeight * 0.18,
    chestDepth, waistDepth, pelvisDepth, pecBoost, hipBoost,
    upperArmTop: lt * 0.58, upperArmMid: lt * 0.5, upperArmBot: lt * 0.42,
    lowerArmTop: lt * 0.4, lowerArmMid: lt * 0.36, lowerArmBot: lt * 0.3,
    upperLegTop: lt * 0.68, upperLegMid: lt * 0.58, upperLegBot: lt * 0.48,
    lowerLegTop: lt * 0.46, lowerLegMid: lt * 0.4, lowerLegBot: lt * 0.32,
    handPalmWidth: lt * 0.92, handPalmHeight: lt * 0.78, handPalmDepth: lt * 1.35,
    footWidth: lt * 1.12, footLength: lt * 2.25, footHeight: lt * 0.5,
    deltoid: lt * 0.55,
  };
}

export type BuiltHumanMesh = {
  metadata: HumanMeshMetadata;
  meshes: Mesh[];
};

export function buildHumanBody(
  scene: Scene,
  figureId: string,
  spec: ArchetypeSpec,
  joints: JointNodes,
  material: StandardMaterial,
): BuiltHumanMesh {
  const p = tuneProportions(spec);
  const meshes: Mesh[] = [];

  meshes.push(ringTorso(scene, joints.pelvis, figureId, "pelvis", [
    { y: 0.02, rx: p.pelvisTop * p.hipBoost, rz: p.pelvisDepth },
    { y: -p.pelvisH * 0.22, rx: p.pelvisMid * p.hipBoost, rz: p.pelvisDepth * 1.04 },
    { y: -p.pelvisH * 0.48, rx: p.pelvisMid * 0.98, rz: p.pelvisDepth * 1.0 },
    { y: -p.pelvisH * 0.74, rx: p.pelvisBot, rz: p.pelvisDepth * 0.9 },
    { y: -p.pelvisH, rx: p.pelvisBot * 0.88, rz: p.pelvisDepth * 0.78 },
  ], 16, material));

  meshes.push(ringTorso(scene, joints.spine, figureId, "spine", [
    { y: p.waistH * 0.15, rx: p.waistTop, rz: p.waistDepth },
    { y: -p.waistH * 0.18, rx: p.waistMid * 0.98, rz: p.waistDepth * 0.94 },
    { y: -p.waistH * 0.42, rx: p.waistMid, rz: p.waistDepth * 0.96 },
    { y: -p.waistH * 0.72, rx: p.waistBot, rz: p.waistDepth * 0.98 },
    { y: -p.waistH, rx: p.pelvisTop * 0.92, rz: p.pelvisDepth * 0.9 },
  ], 16, material));

  meshes.push(ringTorso(scene, joints.chest, figureId, "chest", [
    { y: p.chestH * 0.12, rx: p.chestTop, rz: p.chestDepth * 0.86 },
    { y: -p.chestH * 0.08, rx: p.chestMid * p.pecBoost, rz: p.chestDepth * 1.02 },
    { y: -p.chestH * 0.28, rx: p.chestMid * p.pecBoost, rz: p.chestDepth },
    { y: -p.chestH * 0.58, rx: p.chestBot, rz: p.chestDepth * 0.92 },
    { y: -p.chestH, rx: p.waistTop, rz: p.waistDepth },
  ], 16, material));

  const leftDelt = MeshBuilder.CreateIcoSphere(`${figureId}-body-leftUpperArm-delt`, { radius: p.deltoid, subdivisions: 2 }, scene);
  leftDelt.parent = joints.leftShoulder;
  leftDelt.position.y = -p.deltoid * 0.15;
  flatShade(leftDelt);
  leftDelt.material = material;
  leftDelt.isPickable = true;
  leftDelt.metadata = { figureId, region: "leftUpperArm", kind: "body" };
  meshes.push(leftDelt);

  const rightDelt = MeshBuilder.CreateIcoSphere(`${figureId}-body-rightUpperArm-delt`, { radius: p.deltoid, subdivisions: 2 }, scene);
  rightDelt.parent = joints.rightShoulder;
  rightDelt.position.y = -p.deltoid * 0.15;
  flatShade(rightDelt);
  rightDelt.material = material;
  rightDelt.isPickable = true;
  rightDelt.metadata = { figureId, region: "rightUpperArm", kind: "body" };
  meshes.push(rightDelt);

  meshes.push(createNeck(scene, joints.neck, figureId, { height: p.neckLength, radius: p.neckRadius }, material));
  meshes.push(createFacetedHead(scene, joints.head, figureId, p.headRadius, material));

  meshes.push(createAnatomicalLimb(scene, joints.leftShoulder, figureId, "leftUpperArm", {
    length: spec.upperArm, top: p.upperArmTop, mid: p.upperArmMid, bottom: p.upperArmBot, y: -spec.upperArm / 2,
  }, material));
  meshes.push(createAnatomicalLimb(scene, joints.leftElbow, figureId, "leftLowerArm", {
    length: spec.lowerArm, top: p.lowerArmTop, mid: p.lowerArmMid, bottom: p.lowerArmBot, y: -spec.lowerArm / 2,
  }, material));
  meshes.push(createFacetedHand(scene, joints.leftWrist, figureId, "leftHand", {
    palmW: p.handPalmWidth, palmH: p.handPalmHeight, palmD: p.handPalmDepth, side: -1,
  }, material));

  meshes.push(createAnatomicalLimb(scene, joints.rightShoulder, figureId, "rightUpperArm", {
    length: spec.upperArm, top: p.upperArmTop, mid: p.upperArmMid, bottom: p.upperArmBot, y: -spec.upperArm / 2,
  }, material));
  meshes.push(createAnatomicalLimb(scene, joints.rightElbow, figureId, "rightLowerArm", {
    length: spec.lowerArm, top: p.lowerArmTop, mid: p.lowerArmMid, bottom: p.lowerArmBot, y: -spec.lowerArm / 2,
  }, material));
  meshes.push(createFacetedHand(scene, joints.rightWrist, figureId, "rightHand", {
    palmW: p.handPalmWidth, palmH: p.handPalmHeight, palmD: p.handPalmDepth, side: 1,
  }, material));

  meshes.push(createAnatomicalLimb(scene, joints.leftHip, figureId, "leftUpperLeg", {
    length: spec.upperLeg, top: p.upperLegTop, mid: p.upperLegMid, bottom: p.upperLegBot, y: -spec.upperLeg / 2,
  }, material));
  meshes.push(createAnatomicalLimb(scene, joints.leftKnee, figureId, "leftLowerLeg", {
    length: spec.lowerLeg, top: p.lowerLegTop, mid: p.lowerLegMid, bottom: p.lowerLegBot, y: -spec.lowerLeg / 2,
  }, material));
  meshes.push(createFacetedFoot(scene, joints.leftAnkle, figureId, "leftFoot", {
    width: p.footWidth, length: p.footLength, height: p.footHeight,
  }, material));

  meshes.push(createAnatomicalLimb(scene, joints.rightHip, figureId, "rightUpperLeg", {
    length: spec.upperLeg, top: p.upperLegTop, mid: p.upperLegMid, bottom: p.upperLegBot, y: -spec.upperLeg / 2,
  }, material));
  meshes.push(createAnatomicalLimb(scene, joints.rightKnee, figureId, "rightLowerLeg", {
    length: spec.lowerLeg, top: p.lowerLegTop, mid: p.lowerLegMid, bottom: p.lowerLegBot, y: -spec.lowerLeg / 2,
  }, material));
  meshes.push(createFacetedFoot(scene, joints.rightAnkle, figureId, "rightFoot", {
    width: p.footWidth, length: p.footLength, height: p.footHeight,
  }, material));

  const triangleCount = meshes.reduce((sum, mesh) => sum + countMeshTriangles(mesh), 0);
  return {
    metadata: buildHumanMeshMetadata(spec.id, triangleCount, spec.height),
    meshes,
  };
}

export function regionFromMeshName(meshName: string): BodyRegion | null {
  const m = meshName.match(/-body-([a-zA-Z]+)(-thumb|-f\d|-delt)?$/);
  if (!m) return null;
  return m[1] as BodyRegion;
}

export function figureExportMetadata(archetypeId: ArchetypeId, heightM: number, triangleCount: number) {
  const id = figureIdentity(archetypeId);
  return {
    gender: id.gender,
    ageClass: id.ageClass,
    heightM,
    triangleCount,
    jointCount: 17,
    rig: "posecraft-v2",
    uv: "generated",
    modelId: getHumanModelId(archetypeId),
    shading: "flat-faceted",
    pose: "T-pose",
  };
}
