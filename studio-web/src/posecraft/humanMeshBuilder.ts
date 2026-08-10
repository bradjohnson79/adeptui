/**
 * PoseCraft — Low-poly human figure mesh builder (Final Mandatory GO, D1–D4).
 *
 * Procedurally constructs faceted, flat-shaded low-poly humanoid body meshes
 * parented to an existing 17-joint TransformNode rig. The builder does NOT own
 * the rig (the rig is created by `createFigureRig` in engine.ts and preserved
 * for pose catalog / gizmo / API stability); it only owns the body geometry
 * and the region→joint pick mapping.
 *
 * Art direction (from docs/release-gate/posecraft/refs/human-figures/):
 *  - Faceted head (low-subdivision icosphere), short neck
 *  - Shaped chest / waist / pelvis (male V-taper, female waist-hip, children
 *    larger head + shorter limbs; boy ≠ girl)
 *  - Tapered limb segments (low-tessellation cylinders, flat-shaded)
 *  - Mitt hands (palm block + thumb block) and wedge feet (triangular prism)
 *  - Flat shading so each polygonal facet reads clearly
 *
 * Metadata exposed per figure: modelId, jointCount, bodyRegions[],
 * legacyBlockModel: false.
 */
import {
  Mesh,
  MeshBuilder,
  Scene,
  StandardMaterial,
  TransformNode,
  VertexData,
} from "@babylonjs/core";
import type { ArchetypeSpec, JointName } from "./types";

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
};

export const HUMAN_MODEL_IDS = {
  "adult-male": "adult-male-lowpoly-v2",
  "adult-female": "adult-female-lowpoly-v2",
  "child-boy": "child-boy-lowpoly-v2",
  "child-girl": "child-girl-lowpoly-v2",
} as const;

export function getHumanModelId(archetypeId: ArchetypeSpec["id"]): string {
  return HUMAN_MODEL_IDS[archetypeId] ?? "adult-male-lowpoly-v2";
}

export function buildHumanMeshMetadata(archetypeId: ArchetypeSpec["id"]): HumanMeshMetadata {
  return {
    modelId: getHumanModelId(archetypeId),
    jointCount: 17,
    bodyRegions: [...BODY_REGIONS],
    legacyBlockModel: false as const,
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

function torsoDepth(spec: ArchetypeSpec): number {
  // Front-back depth of torso segments, derived from archetype proportions.
  return Math.max(spec.shoulderWidth, spec.hipWidth) * 0.58;
}

function createTaperedLimb(
  scene: Scene, parent: TransformNode, figureId: string, region: BodyRegion,
  options: { length: number; topRadius: number; bottomRadius: number; y: number },
  material: StandardMaterial,
): Mesh {
  const mesh = MeshBuilder.CreateCylinder(`${figureId}-body-${region}`, {
    height: options.length,
    diameterTop: options.topRadius * 2,
    diameterBottom: options.bottomRadius * 2,
    tessellation: 6,
  }, scene);
  mesh.parent = parent;
  mesh.position.y = options.y;
  flatShade(mesh);
  tagMesh(mesh, figureId, region, material);
  return mesh;
}

function createTorsoSegment(
  scene: Scene, parent: TransformNode, figureId: string, region: BodyRegion,
  options: { topWidth: number; bottomWidth: number; height: number; depth: number; y: number },
  material: StandardMaterial,
): Mesh {
  const mesh = MeshBuilder.CreateCylinder(`${figureId}-body-${region}`, {
    height: options.height,
    diameterTop: options.topWidth,
    diameterBottom: options.bottomWidth,
    tessellation: 8,
  }, scene);
  mesh.parent = parent;
  mesh.position.y = options.y;
  const base = Math.max(options.topWidth, options.bottomWidth);
  mesh.scaling.z = options.depth / base;
  flatShade(mesh);
  tagMesh(mesh, figureId, region, material);
  return mesh;
}

function createFacetedHead(
  scene: Scene, parent: TransformNode, figureId: string, radius: number, material: StandardMaterial,
): Mesh {
  const mesh = MeshBuilder.CreateIcoSphere(`${figureId}-body-head`, { radius, subdivisions: 1 }, scene);
  mesh.parent = parent;
  mesh.position.y = radius * 0.55;
  flatShade(mesh);
  tagMesh(mesh, figureId, "head", material);
  return mesh;
}

function createNeck(
  scene: Scene, parent: TransformNode, figureId: string,
  options: { height: number; radius: number }, material: StandardMaterial,
): Mesh {
  const mesh = MeshBuilder.CreateCylinder(`${figureId}-body-neck`, {
    height: options.height, diameter: options.radius * 2, tessellation: 6,
  }, scene);
  mesh.parent = parent;
  mesh.position.y = options.height / 2;
  flatShade(mesh);
  tagMesh(mesh, figureId, "neck", material);
  return mesh;
}

function createMittHand(
  scene: Scene, parent: TransformNode, figureId: string, region: BodyRegion,
  options: { palmWidth: number; palmHeight: number; palmDepth: number; thumbWidth: number; thumbDepth: number; side: 1 | -1 },
  material: StandardMaterial,
): Mesh {
  const palm = MeshBuilder.CreateBox(`${figureId}-body-${region}`, {
    width: options.palmWidth, height: options.palmHeight, depth: options.palmDepth,
  }, scene);
  palm.parent = parent;
  palm.position.y = -options.palmHeight / 2;
  palm.position.z = options.palmDepth * 0.15;
  flatShade(palm);
  tagMesh(palm, figureId, region, material);

  const thumb = MeshBuilder.CreateBox(`${figureId}-body-${region}-thumb`, {
    width: options.thumbWidth, height: options.palmHeight * 0.7, depth: options.thumbDepth,
  }, scene);
  thumb.parent = parent;
  thumb.position.x = options.side * (options.palmWidth / 2 + options.thumbWidth / 2 * 0.6);
  thumb.position.y = -options.palmHeight * 0.1;
  thumb.position.z = options.palmDepth * 0.55;
  thumb.rotation.z = options.side * -0.5;
  flatShade(thumb);
  thumb.material = material;
  thumb.isPickable = true;
  thumb.metadata = { figureId, region, kind: "body" };
  return palm;
}

function createWedgeFoot(
  scene: Scene, parent: TransformNode, figureId: string, region: BodyRegion,
  options: { width: number; length: number; height: number }, material: StandardMaterial,
): Mesh {
  const w = options.width;
  const l = options.length;
  const h = options.height;
  const positions = [
    -w / 2, 0, -l / 2, // 0 BBL
    w / 2, 0, -l / 2,  // 1 BBR
    -w / 2, 0, l / 2,  // 2 FBL
    w / 2, 0, l / 2,   // 3 FBR
    -w / 2, h, -l / 2, // 4 BTL
    w / 2, h, -l / 2,  // 5 BTR
  ];
  const indices = [
    0, 2, 3, 0, 3, 1,         // bottom
    0, 1, 5, 0, 5, 4,         // back
    4, 5, 3, 4, 3, 2,         // top slope
    0, 4, 2,                 // left side
    1, 3, 5,                 // right side
  ];
  const normals: number[] = [];
  const vertexData = new VertexData();
  vertexData.positions = positions;
  vertexData.indices = indices;
  VertexData.ComputeNormals(positions, indices, normals);
  vertexData.normals = normals;
  const mesh = new Mesh(`${figureId}-body-${region}`, scene);
  vertexData.applyToMesh(mesh);
  mesh.parent = parent;
  mesh.position.y = -h * 0.1;
  mesh.position.z = l * 0.25;
  mesh.material = material;
  mesh.isPickable = true;
  mesh.metadata = { figureId, region, kind: "body" };
  mesh.receiveShadows = false;
  mesh.convertToFlatShadedMesh();
  return mesh;
}

type ProportionTuning = {
  headRadius: number; neckRadius: number; neckLength: number;
  chestTopWidth: number; chestBottomWidth: number; chestHeight: number;
  waistTopWidth: number; waistBottomWidth: number; waistHeight: number;
  pelvisTopWidth: number; pelvisBottomWidth: number; pelvisHeight: number;
  upperArmTopRadius: number; upperArmBottomRadius: number;
  lowerArmTopRadius: number; lowerArmBottomRadius: number;
  upperLegTopRadius: number; upperLegBottomRadius: number;
  lowerLegTopRadius: number; lowerLegBottomRadius: number;
  handPalmWidth: number; handPalmHeight: number; handPalmDepth: number;
  footWidth: number; footLength: number; footHeight: number;
};

function tuneProportions(spec: ArchetypeSpec): ProportionTuning {
  const h = spec.height;
  const sw = spec.shoulderWidth;
  const hw = spec.hipWidth;
  const lt = spec.limbThickness;
  const isChild = spec.id === "child-boy" || spec.id === "child-girl";

  const headRadius = isChild ? h * 0.11 : h * 0.075;
  const neckRadius = sw * 0.16;
  const neckLength = spec.torsoHeight * 0.13;

  let chestTopWidth: number; let chestBottomWidth: number;
  let waistTopWidth: number; let waistBottomWidth: number;
  let pelvisTopWidth: number; let pelvisBottomWidth: number;

  if (spec.id === "adult-male") {
    chestTopWidth = sw; chestBottomWidth = sw * 0.74;
    waistTopWidth = sw * 0.72; waistBottomWidth = hw * 0.96;
    pelvisTopWidth = hw * 0.98; pelvisBottomWidth = hw;
  } else if (spec.id === "adult-female") {
    chestTopWidth = sw; chestBottomWidth = sw * 0.78;
    waistTopWidth = sw * 0.66; waistBottomWidth = sw * 0.7;
    pelvisTopWidth = hw * 1.04; pelvisBottomWidth = hw;
  } else if (spec.id === "child-boy") {
    chestTopWidth = sw; chestBottomWidth = sw * 0.82;
    waistTopWidth = sw * 0.8; waistBottomWidth = sw * 0.82;
    pelvisTopWidth = hw * 0.92; pelvisBottomWidth = hw;
  } else {
    chestTopWidth = sw * 0.94; chestBottomWidth = sw * 0.8;
    waistTopWidth = sw * 0.74; waistBottomWidth = sw * 0.8;
    pelvisTopWidth = hw * 1.02; pelvisBottomWidth = hw;
  }

  return {
    headRadius, neckRadius, neckLength,
    chestTopWidth, chestBottomWidth, chestHeight: spec.torsoHeight * 0.38,
    waistTopWidth, waistBottomWidth, waistHeight: spec.torsoHeight * 0.24,
    pelvisTopWidth, pelvisBottomWidth, pelvisHeight: spec.torsoHeight * 0.16,
    upperArmTopRadius: lt * 0.56, upperArmBottomRadius: lt * 0.44,
    lowerArmTopRadius: lt * 0.42, lowerArmBottomRadius: lt * 0.34,
    upperLegTopRadius: lt * 0.64, upperLegBottomRadius: lt * 0.5,
    lowerLegTopRadius: lt * 0.48, lowerLegBottomRadius: lt * 0.36,
    handPalmWidth: lt * 0.95, handPalmHeight: lt * 0.9, handPalmDepth: lt * 1.5,
    footWidth: lt * 1.15, footLength: lt * 2.1, footHeight: lt * 0.55,
  };
}

export type BuiltHumanMesh = {
  metadata: HumanMeshMetadata;
  meshes: Mesh[];
};

/**
 * Build the full low-poly human body for a figure, parenting body meshes to
 * the existing 17-joint TransformNode rig. The pelvis joint sits at hipHeight;
 * torso segments stack upward from there, limbs hang downward from shoulder/
 * hip joints. Returns metadata + the list of body meshes (for disposal).
 */
export function buildHumanBody(
  scene: Scene,
  figureId: string,
  spec: ArchetypeSpec,
  joints: JointNodes,
  material: StandardMaterial,
): BuiltHumanMesh {
  const p = tuneProportions(spec);
  const depth = torsoDepth(spec);
  const meshes: Mesh[] = [];

  // Pelvis segment hangs just below the pelvis joint.
  meshes.push(createTorsoSegment(scene, joints.pelvis, figureId, "pelvis", {
    topWidth: p.pelvisTopWidth, bottomWidth: p.pelvisBottomWidth,
    height: p.pelvisHeight, depth, y: -p.pelvisHeight / 2,
  }, material));
  // Spine/waist hangs below the spine joint.
  meshes.push(createTorsoSegment(scene, joints.spine, figureId, "spine", {
    topWidth: p.waistTopWidth, bottomWidth: p.waistBottomWidth,
    height: p.waistHeight, depth, y: -p.waistHeight / 2,
  }, material));
  // Chest hangs below the chest joint.
  meshes.push(createTorsoSegment(scene, joints.chest, figureId, "chest", {
    topWidth: p.chestTopWidth, bottomWidth: p.chestBottomWidth,
    height: p.chestHeight, depth, y: -p.chestHeight / 2,
  }, material));
  // Neck + head.
  meshes.push(createNeck(scene, joints.neck, figureId, {
    height: p.neckLength, radius: p.neckRadius,
  }, material));
  meshes.push(createFacetedHead(scene, joints.head, figureId, p.headRadius, material));

  // Arms.
  meshes.push(createTaperedLimb(scene, joints.leftShoulder, figureId, "leftUpperArm", {
    length: spec.upperArm, topRadius: p.upperArmTopRadius, bottomRadius: p.upperArmBottomRadius,
    y: -spec.upperArm / 2,
  }, material));
  meshes.push(createTaperedLimb(scene, joints.leftElbow, figureId, "leftLowerArm", {
    length: spec.lowerArm, topRadius: p.lowerArmTopRadius, bottomRadius: p.lowerArmBottomRadius,
    y: -spec.lowerArm / 2,
  }, material));
  meshes.push(createMittHand(scene, joints.leftWrist, figureId, "leftHand", {
    palmWidth: p.handPalmWidth, palmHeight: p.handPalmHeight, palmDepth: p.handPalmDepth,
    thumbWidth: p.handPalmWidth * 0.4, thumbDepth: p.handPalmDepth * 0.6, side: -1,
  }, material));

  meshes.push(createTaperedLimb(scene, joints.rightShoulder, figureId, "rightUpperArm", {
    length: spec.upperArm, topRadius: p.upperArmTopRadius, bottomRadius: p.upperArmBottomRadius,
    y: -spec.upperArm / 2,
  }, material));
  meshes.push(createTaperedLimb(scene, joints.rightElbow, figureId, "rightLowerArm", {
    length: spec.lowerArm, topRadius: p.lowerArmTopRadius, bottomRadius: p.lowerArmBottomRadius,
    y: -spec.lowerArm / 2,
  }, material));
  meshes.push(createMittHand(scene, joints.rightWrist, figureId, "rightHand", {
    palmWidth: p.handPalmWidth, palmHeight: p.handPalmHeight, palmDepth: p.handPalmDepth,
    thumbWidth: p.handPalmWidth * 0.4, thumbDepth: p.handPalmDepth * 0.6, side: 1,
  }, material));

  // Legs.
  meshes.push(createTaperedLimb(scene, joints.leftHip, figureId, "leftUpperLeg", {
    length: spec.upperLeg, topRadius: p.upperLegTopRadius, bottomRadius: p.upperLegBottomRadius,
    y: -spec.upperLeg / 2,
  }, material));
  meshes.push(createTaperedLimb(scene, joints.leftKnee, figureId, "leftLowerLeg", {
    length: spec.lowerLeg, topRadius: p.lowerLegTopRadius, bottomRadius: p.lowerLegBottomRadius,
    y: -spec.lowerLeg / 2,
  }, material));
  meshes.push(createWedgeFoot(scene, joints.leftAnkle, figureId, "leftFoot", {
    width: p.footWidth, length: p.footLength, height: p.footHeight,
  }, material));

  meshes.push(createTaperedLimb(scene, joints.rightHip, figureId, "rightUpperLeg", {
    length: spec.upperLeg, topRadius: p.upperLegTopRadius, bottomRadius: p.upperLegBottomRadius,
    y: -spec.upperLeg / 2,
  }, material));
  meshes.push(createTaperedLimb(scene, joints.rightKnee, figureId, "rightLowerLeg", {
    length: spec.lowerLeg, topRadius: p.lowerLegTopRadius, bottomRadius: p.lowerLegBottomRadius,
    y: -spec.lowerLeg / 2,
  }, material));
  meshes.push(createWedgeFoot(scene, joints.rightAnkle, figureId, "rightFoot", {
    width: p.footWidth, length: p.footLength, height: p.footHeight,
  }, material));

  return { metadata: buildHumanMeshMetadata(spec.id), meshes };
}

/** Resolve a picked mesh's region to its pose joint, if it is a body mesh. */
export function regionFromMeshName(meshName: string): BodyRegion | null {
  const m = meshName.match(/-body-([a-zA-Z]+)(-thumb)?$/);
  if (!m) return null;
  return m[1] as BodyRegion;
}
