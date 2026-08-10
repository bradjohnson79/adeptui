import {
  AbstractEngine,
  ArcRotateCamera,
  Color3,
  Color4,
  Engine,
  HemisphericLight,
  Matrix,
  Mesh,
  MeshBuilder,
  PointerEventTypes,
  Scene,
  SceneLoader,
  StandardMaterial,
  TransformNode,
  Vector3,
} from "@babylonjs/core";
// Final Mandatory GO (IMPORT): register Babylon mesh loaders for custom
// figure import (glTF/GLB + OBJ). FBX has no first-party Babylon loader and
// will surface a creator-facing error via the SceneLoader onError callback.
import "@babylonjs/loaders/OBJ";
import "@babylonjs/loaders/glTF";
import { getArchetypeSpec, getColorSpec } from "./state";
import { apiUrl } from "../runtime/apiBase";
import {
  BODY_REGIONS,
  REGION_TO_JOINT,
  buildHumanBody,
  regionFromMeshName,
  type BuiltHumanMesh,
} from "./humanMeshBuilder";
import type { FigureInstance, JointName, PoseCraftScene } from "./types";

type RendererKind = "webgl" | "webgpu";

export type GizmoMode = "move" | "rotate" | "pose";

export type ManipulationEvent =
  | { kind: "select"; figureId: string | null }
  | { kind: "move"; figureId: string; position: { x: number; z: number } }
  | { kind: "rotate"; figureId: string; rotationY: number }
  | { kind: "pose"; figureId: string; joint: JointName; rotation: { x: number; y: number; z: number } };

type FigureRig = {
  root: TransformNode;
  joints: Record<JointName, TransformNode>;
  material: StandardMaterial;
  ringMaterial: StandardMaterial;
  selectionRing: TransformNode;
  handles: Record<JointName, Mesh>;
  handleMaterial: StandardMaterial;
  /** Final Mandatory GO: low-poly human body meshes + metadata. */
  bodyMeshes: Mesh[];
  metadata: BuiltHumanMesh["metadata"];
};

type PrimitiveRig = {
  root: TransformNode;
  material: StandardMaterial;
};

// ---------------------------------------------------------------------------
// Gate F — Visible on-canvas gizmos. The Move gizmo exposes XYZ axis arrows
// (pickable handles), the Rotate gizmo exposes XYZ rings, and the Pose Body
// gizmo exposes a rotation ring at the selected joint. Handles are named so
// Playwright can identify them and perform real pointer drags.
// ---------------------------------------------------------------------------
type AxisGizmo = {
  root: TransformNode;
  handles: { x: Mesh; y: Mesh; z: Mesh };
  materials: { x: StandardMaterial; y: StandardMaterial; z: StandardMaterial };
};

const GIZMO_AXIS_COLORS = {
  x: new Color3(0.85, 0.22, 0.18),
  y: new Color3(0.22, 0.7, 0.34),
  z: new Color3(0.18, 0.45, 0.86),
};

function createAxisArrow(scene: Scene, parent: TransformNode, axis: "x" | "y" | "z", length: number, name: string, material: StandardMaterial): Mesh {
  // A pickable handle: a thick cylinder shaft + a cone tip along the axis.
  // We parent both to a TransformNode but return the shaft as the pickable
  // (the cone is pickable too via metadata). For simplicity, build one
  // merged-looking handle: a cylinder for the shaft and a cone for the tip,
  // both parented to the same TransformNode; we return the shaft and set the
  // cone's parent to the shaft so picking either resolves to the shaft name.
  const shaft = MeshBuilder.CreateCylinder(`${name}-shaft`, {
    height: length * 0.78,
    diameter: 0.12,
    tessellation: 8,
  }, scene);
  shaft.material = material;
  shaft.isPickable = true;

  const tip = MeshBuilder.CreateCylinder(`${name}-tip`, {
    height: length * 0.22,
    diameterTop: 0,
    diameterBottom: 0.2,
    tessellation: 8,
  }, scene);
  tip.material = material;
  tip.isPickable = true;
  tip.parent = shaft;

  // Orient along the axis. Babylon cylinders are along Y by default.
  if (axis === "x") {
    shaft.rotation.z = Math.PI / 2; // lay along X
  } else if (axis === "z") {
    shaft.rotation.x = Math.PI / 2; // lay along Z
  }
  // Position so the handle starts at the gizmo origin and extends outward.
  // After rotation, the cylinder center is at length/2 along the axis.
  if (axis === "x") {
    shaft.position.x = length / 2;
    tip.position.y = length / 2; // tip at the far end (relative to shaft top)
  } else if (axis === "y") {
    shaft.position.y = length / 2;
    tip.position.y = length / 2;
  } else {
    shaft.position.z = length / 2;
    tip.position.y = length / 2;
  }

  shaft.parent = parent;
  return shaft;
}

function createRotateRing(scene: Scene, parent: TransformNode, axis: "x" | "y" | "z", diameter: number, name: string, material: StandardMaterial): Mesh {
  const ring = MeshBuilder.CreateTorus(`${name}`, {
    diameter,
    thickness: 0.04,
    tessellation: 32,
  }, scene);
  ring.material = material;
  ring.isPickable = true;
  // Torus is in the XZ plane by default. Orient to the axis plane:
  // X ring → YZ plane (rotate around X by 90°) → rotate.x = π/2
  // Y ring → XZ plane (default) → no rotation
  // Z ring → XY plane (rotate around Z by 90°) → rotate.y = π/2
  if (axis === "x") ring.rotation.x = Math.PI / 2;
  else if (axis === "z") ring.rotation.y = Math.PI / 2;
  ring.parent = parent;
  return ring;
}

function createMoveGizmo(scene: Scene): AxisGizmo {
  const root = new TransformNode("posecraft-gizmo-move-root", scene);
  const length = 1.4;
  const matX = new StandardMaterial("posecraft-gizmo-move-mat-x", scene);
  matX.diffuseColor = GIZMO_AXIS_COLORS.x;
  matX.emissiveColor = GIZMO_AXIS_COLORS.x.scale(0.4);
  const matY = new StandardMaterial("posecraft-gizmo-move-mat-y", scene);
  matY.diffuseColor = GIZMO_AXIS_COLORS.y;
  matY.emissiveColor = GIZMO_AXIS_COLORS.y.scale(0.4);
  const matZ = new StandardMaterial("posecraft-gizmo-move-mat-z", scene);
  matZ.diffuseColor = GIZMO_AXIS_COLORS.z;
  matZ.emissiveColor = GIZMO_AXIS_COLORS.z.scale(0.4);
  const x = createAxisArrow(scene, root, "x", length, "posecraft-gizmo-move-x", matX);
  const y = createAxisArrow(scene, root, "y", length, "posecraft-gizmo-move-y", matY);
  const z = createAxisArrow(scene, root, "z", length, "posecraft-gizmo-move-z", matZ);
  root.setEnabled(false);
  return { root, handles: { x, y, z }, materials: { x: matX, y: matY, z: matZ } };
}

function createRotateGizmo(scene: Scene): AxisGizmo {
  const root = new TransformNode("posecraft-gizmo-rotate-root", scene);
  const diameter = 1.6;
  const matX = new StandardMaterial("posecraft-gizmo-rotate-mat-x", scene);
  matX.diffuseColor = GIZMO_AXIS_COLORS.x;
  matX.emissiveColor = GIZMO_AXIS_COLORS.x.scale(0.4);
  matX.alpha = 0.85;
  const matY = new StandardMaterial("posecraft-gizmo-rotate-mat-y", scene);
  matY.diffuseColor = GIZMO_AXIS_COLORS.y;
  matY.emissiveColor = GIZMO_AXIS_COLORS.y.scale(0.4);
  matY.alpha = 0.85;
  const matZ = new StandardMaterial("posecraft-gizmo-rotate-mat-z", scene);
  matZ.diffuseColor = GIZMO_AXIS_COLORS.z;
  matZ.emissiveColor = GIZMO_AXIS_COLORS.z.scale(0.4);
  matZ.alpha = 0.85;
  const x = createRotateRing(scene, root, "x", diameter, "posecraft-gizmo-rotate-x", matX);
  const y = createRotateRing(scene, root, "y", diameter, "posecraft-gizmo-rotate-y", matY);
  const z = createRotateRing(scene, root, "z", diameter, "posecraft-gizmo-rotate-z", matZ);
  root.setEnabled(false);
  return { root, handles: { x, y, z }, materials: { x: matX, y: matY, z: matZ } };
}

function createPoseRing(scene: Scene): { root: TransformNode; ring: Mesh; material: StandardMaterial } {
  const root = new TransformNode("posecraft-gizmo-pose-root", scene);
  const material = new StandardMaterial("posecraft-gizmo-pose-mat", scene);
  material.diffuseColor = new Color3(1, 0.78, 0.2);
  material.emissiveColor = new Color3(0.55, 0.4, 0.08);
  material.alpha = 0.9;
  const ring = MeshBuilder.CreateTorus("posecraft-gizmo-pose-ring", {
    diameter: 0.5,
    thickness: 0.035,
    tessellation: 28,
  }, scene);
  ring.material = material;
  ring.isPickable = true;
  ring.parent = root;
  root.setEnabled(false);
  return { root, ring, material };
}

export type PoseCraftViewportStatus = {
  renderer: RendererKind;
  detail: string;
};

function degreesToRadians(value: number) {
  return (value * Math.PI) / 180;
}

function lensToFov(lensMm: number) {
  return 2 * Math.atan(36 / (2 * lensMm));
}

function colorFromHex(hex: string) {
  return Color3.FromHexString(hex);
}

function createMaterial(scene: Scene, name: string, hex: string) {
  const material = new StandardMaterial(name, scene);
  const color = colorFromHex(hex);
  material.diffuseColor = color;
  material.specularColor = new Color3(0.06, 0.06, 0.06);
  material.emissiveColor = color.scale(0.08);
  return material;
}

function createFigureRig(scene: Scene, figure: FigureInstance): FigureRig {
  const spec = getArchetypeSpec(figure.archetypeId);
  const material = createMaterial(scene, `${figure.id}-material`, getColorSpec(figure.colorId).hex);
  const ringMaterial = new StandardMaterial(`${figure.id}-ring`, scene);
  ringMaterial.diffuseColor = new Color3(1, 1, 1);
  ringMaterial.emissiveColor = new Color3(0.7, 0.95, 1);
  ringMaterial.alpha = 0.25;

  const root = new TransformNode(`${figure.id}-root`, scene);
  const pelvis = new TransformNode(`${figure.id}-pelvis`, scene);
  const spine = new TransformNode(`${figure.id}-spine`, scene);
  const chest = new TransformNode(`${figure.id}-chest`, scene);
  const neck = new TransformNode(`${figure.id}-neck`, scene);
  const head = new TransformNode(`${figure.id}-head`, scene);
  const leftShoulder = new TransformNode(`${figure.id}-leftShoulder`, scene);
  const leftElbow = new TransformNode(`${figure.id}-leftElbow`, scene);
  const leftWrist = new TransformNode(`${figure.id}-leftWrist`, scene);
  const rightShoulder = new TransformNode(`${figure.id}-rightShoulder`, scene);
  const rightElbow = new TransformNode(`${figure.id}-rightElbow`, scene);
  const rightWrist = new TransformNode(`${figure.id}-rightWrist`, scene);
  const leftHip = new TransformNode(`${figure.id}-leftHip`, scene);
  const leftKnee = new TransformNode(`${figure.id}-leftKnee`, scene);
  const leftAnkle = new TransformNode(`${figure.id}-leftAnkle`, scene);
  const rightHip = new TransformNode(`${figure.id}-rightHip`, scene);
  const rightKnee = new TransformNode(`${figure.id}-rightKnee`, scene);
  const rightAnkle = new TransformNode(`${figure.id}-rightAnkle`, scene);
  const selectionRing = new TransformNode(`${figure.id}-selection`, scene);

  const hipHeight = spec.upperLeg + spec.lowerLeg;
  const lowerTorso = spec.torsoHeight * 0.42;
  const upperTorso = spec.torsoHeight * 0.38;
  const neckLength = spec.torsoHeight * 0.14;
  const headRadius = spec.height * 0.07;
  const shoulderHalf = spec.shoulderWidth / 2;
  const hipHalf = spec.hipWidth / 2;

  pelvis.parent = root;
  pelvis.position.y = hipHeight;

  spine.parent = pelvis;
  spine.position.y = lowerTorso;

  chest.parent = spine;
  chest.position.y = upperTorso;

  neck.parent = chest;
  neck.position.y = neckLength;

  head.parent = neck;
  head.position.y = headRadius * 0.95;

  leftShoulder.parent = chest;
  leftShoulder.position.x = -shoulderHalf;
  leftShoulder.position.y = spec.torsoHeight * 0.08;

  leftElbow.parent = leftShoulder;
  leftElbow.position.y = -spec.upperArm;

  leftWrist.parent = leftElbow;
  leftWrist.position.y = -spec.lowerArm;

  rightShoulder.parent = chest;
  rightShoulder.position.x = shoulderHalf;
  rightShoulder.position.y = spec.torsoHeight * 0.08;

  rightElbow.parent = rightShoulder;
  rightElbow.position.y = -spec.upperArm;

  rightWrist.parent = rightElbow;
  rightWrist.position.y = -spec.lowerArm;

  leftHip.parent = pelvis;
  leftHip.position.x = -hipHalf;

  leftKnee.parent = leftHip;
  leftKnee.position.y = -spec.upperLeg;

  leftAnkle.parent = leftKnee;
  leftAnkle.position.y = -spec.lowerLeg;

  rightHip.parent = pelvis;
  rightHip.position.x = hipHalf;

  rightKnee.parent = rightHip;
  rightKnee.position.y = -spec.upperLeg;

  rightAnkle.parent = rightKnee;
  rightAnkle.position.y = -spec.lowerLeg;

  selectionRing.parent = root;
  const ring = MeshBuilder.CreateTorus(
    `${figure.id}-ring`,
    { diameter: 0.95, thickness: 0.03, tessellation: 24 },
    scene,
  );
  ring.parent = selectionRing;
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.02;
  ring.material = ringMaterial;

  // Master Program: pickable joint handles for Pose Body mode. Small spheres
  // parented to each joint; only enabled when the figure is selected and the
  // gizmo mode is "pose". Named `${figure.id}-handle-${joint}` for picking.
  const handleMaterial = new StandardMaterial(`${figure.id}-handleMat`, scene);
  handleMaterial.diffuseColor = new Color3(1, 0.78, 0.2);
  handleMaterial.emissiveColor = new Color3(0.55, 0.4, 0.08);
  handleMaterial.specularColor = new Color3(0.1, 0.1, 0.1);
  const handleDiameter = Math.max(0.22, spec.limbThickness * 1.4);
  const handles: Record<JointName, Mesh> = {} as Record<JointName, Mesh>;
  const jointNodes: [JointName, TransformNode][] = [
    ["pelvis", pelvis], ["spine", spine], ["chest", chest], ["neck", neck], ["head", head],
    ["leftShoulder", leftShoulder], ["leftElbow", leftElbow], ["leftWrist", leftWrist],
    ["rightShoulder", rightShoulder], ["rightElbow", rightElbow], ["rightWrist", rightWrist],
    ["leftHip", leftHip], ["leftKnee", leftKnee], ["leftAnkle", leftAnkle],
    ["rightHip", rightHip], ["rightKnee", rightKnee], ["rightAnkle", rightAnkle],
  ];
  for (const [jointName, jointNode] of jointNodes) {
    const handle = MeshBuilder.CreateSphere(
      `${figure.id}-handle-${jointName}`,
      { diameter: handleDiameter, segments: 6 },
      scene,
    );
    handle.parent = jointNode;
    handle.position.y = 0;
    handle.material = handleMaterial;
    handle.isPickable = true;
    handle.setEnabled(false);
    handles[jointName] = handle;
  }

  // Final Mandatory GO: low-poly human body built by humanMeshBuilder. The
  // 17-joint TransformNode rig above is preserved; the builder parents faceted
  // body meshes to those joints and exposes modelId / jointCount / bodyRegions
  // metadata + a region→joint pick map. Custom figures skip the builder.
  const built = figure.kind === "custom"
    ? null
    : buildHumanBody(scene, figure.id, spec, {
        pelvis, spine, chest, neck, head,
        leftShoulder, leftElbow, leftWrist,
        rightShoulder, rightElbow, rightWrist,
        leftHip, leftKnee, leftAnkle,
        rightHip, rightKnee, rightAnkle,
      }, material);
  const bodyMeshes = built ? built.meshes : [];
  const metadata = built
    ? built.metadata
    : { modelId: "custom-mesh", jointCount: 17, bodyRegions: BODY_REGIONS, legacyBlockModel: false as const };

  // Final Mandatory GO (IMPORT): custom-mesh figures load their geometry from
  // the project Library asset via Babylon SceneLoader. glTF/GLB and OBJ load
  // through the standard loaders; FBX is best-effort. The loaded meshes are
  // parented to the figure root and tagged as body meshes for picking. Load
  // is async; the rig is returned immediately and the mesh attaches when ready.
  if (figure.kind === "custom" && figure.customAssetId) {
    const assetUrl = apiUrl(`/api/assets/${figure.customAssetId}/file`);
    const rootTransform = root;
    let cancelled = false;
    const finishImport = (meshes: import("@babylonjs/core").AbstractMesh[]) => {
      if (cancelled || rootTransform.isDisposed()) return;
      for (const mesh of meshes) {
        if ((mesh as Mesh).material === null || (mesh as Mesh).material === undefined) {
          (mesh as Mesh).material = material;
        }
        mesh.parent = rootTransform;
        mesh.isPickable = true;
        mesh.metadata = { figureId: figure.id, region: "chest", kind: "body" };
        mesh.name = `${figure.id}-body-custom`;
        bodyMeshes.push(mesh as Mesh);
      }
    };
    SceneLoader.ImportMesh("", "", assetUrl, scene, finishImport, undefined, (_scene, message) => {
      console.error(`PoseCraft custom figure import failed for ${figure.customAssetId}: ${message}`);
    });
    // The returned bodyMeshes array is captured by the closure so late-loaded
    // meshes still register for disposal via the rig.
    void cancelled;
  }

  return {
    root,
    joints: {
      pelvis,
      spine,
      chest,
      neck,
      head,
      leftShoulder,
      leftElbow,
      leftWrist,
      rightShoulder,
      rightElbow,
      rightWrist,
      leftHip,
      leftKnee,
      leftAnkle,
      rightHip,
      rightKnee,
      rightAnkle,
    },
    material,
    ringMaterial,
    selectionRing,
    handles,
    handleMaterial,
    bodyMeshes,
    metadata,
  };
}

function createPrimitiveRig(scene: Scene, primitive: PoseCraftScene["primitives"][number]): PrimitiveRig {
  const root = new TransformNode(`${primitive.id}-root`, scene);
  const material = createMaterial(scene, `${primitive.id}-material`, primitive.color);

  // Gate H — Furniture is rendered as real Babylon geometry:
  //  - blocks (apple-box/cube/platform/block-*) → a single box
  //  - block-chair → seat box + back box
  //  - table-* → tabletop box + four cylindrical legs
  // The primitive.size drives the bounding box; sub-meshes are parented to root.
  const kind = primitive.kind;
  const isChair = kind === "block-chair";
  const isTable = kind === "table-small" || kind === "table-medium" || kind === "table-large";
  const isWall = kind === "wall-small" || kind === "wall-medium" || kind === "wall-large";
  const isWallWindow = kind === "wall-window-small" || kind === "wall-window-medium" || kind === "wall-window-large";

  if (isWall) {
    // Thin tall box, centered on the floor edge.
    const mesh = MeshBuilder.CreateBox(`${primitive.id}-mesh`, {
      width: primitive.size.x,
      height: primitive.size.y,
      depth: primitive.size.z,
    }, scene);
    mesh.parent = root;
    mesh.position.y = primitive.size.y / 2;
    mesh.material = material;
    return { root, material };
  }

  if (isWallWindow) {
    // Wall with a centered window opening: build the wall as four frame bars
    // (top, bottom, left, right) leaving a rectangular opening in the middle.
    // No CSG — compound of boxes reads clearly as a wall-with-window.
    const w = primitive.size.x;
    const h = primitive.size.y;
    const t = primitive.size.z;
    // Window opening covers ~55% width and ~45% height, centered.
    const winW = w * 0.55;
    const winH = h * 0.45;
    const winY = h * 0.55; // center of opening above floor
    const sideW = (w - winW) / 2;
    const topH = (h - winY - winH / 2);
    const bottomH = winY - winH / 2;
    // Left jamb
    const left = MeshBuilder.CreateBox(`${primitive.id}-jamb-left`, { width: sideW, height: h, depth: t }, scene);
    left.parent = root; left.position.y = h / 2; left.position.x = -(w / 2 - sideW / 2); left.material = material;
    // Right jamb
    const right = MeshBuilder.CreateBox(`${primitive.id}-jamb-right`, { width: sideW, height: h, depth: t }, scene);
    right.parent = root; right.position.y = h / 2; right.position.x = (w / 2 - sideW / 2); right.material = material;
    // Top header
    const top = MeshBuilder.CreateBox(`${primitive.id}-header`, { width: winW, height: topH, depth: t }, scene);
    top.parent = root; top.position.y = h - topH / 2; top.material = material;
    // Bottom sill
    const bottom = MeshBuilder.CreateBox(`${primitive.id}-sill`, { width: winW, height: bottomH, depth: t }, scene);
    bottom.parent = root; bottom.position.y = bottomH / 2; bottom.material = material;
    return { root, material };
  }

  if (isChair) {
    const seat = MeshBuilder.CreateBox(`${primitive.id}-seat`, {
      width: primitive.size.x,
      height: Math.max(0.08, primitive.size.y * 0.18),
      depth: primitive.size.z,
    }, scene);
    seat.parent = root;
    seat.position.y = primitive.size.y * 0.5;
    seat.material = material;
    const back = MeshBuilder.CreateBox(`${primitive.id}-back`, {
      width: primitive.size.x,
      height: primitive.size.y * 0.55,
      depth: Math.max(0.06, primitive.size.z * 0.12),
    }, scene);
    back.parent = root;
    back.position.y = primitive.size.y * 0.5 + (primitive.size.y * 0.55) / 2 + (primitive.size.y * 0.18) / 2;
    back.position.z = -primitive.size.z / 2 + Math.max(0.06, primitive.size.z * 0.12) / 2;
    back.material = material;
    return { root, material };
  }

  if (isTable) {
    const topThickness = Math.max(0.06, primitive.size.y * 0.08);
    const top = MeshBuilder.CreateBox(`${primitive.id}-top`, {
      width: primitive.size.x,
      height: topThickness,
      depth: primitive.size.z,
    }, scene);
    top.parent = root;
    top.position.y = primitive.size.y - topThickness / 2;
    top.material = material;
    const legRadius = Math.max(0.03, Math.min(primitive.size.x, primitive.size.z) * 0.06);
    const legHeight = primitive.size.y - topThickness;
    const legInset = Math.min(primitive.size.x, primitive.size.z) * 0.12;
    const legPositions = [
      { x: primitive.size.x / 2 - legInset, z: primitive.size.z / 2 - legInset },
      { x: -primitive.size.x / 2 + legInset, z: primitive.size.z / 2 - legInset },
      { x: primitive.size.x / 2 - legInset, z: -primitive.size.z / 2 + legInset },
      { x: -primitive.size.x / 2 + legInset, z: -primitive.size.z / 2 + legInset },
    ];
    for (let i = 0; i < legPositions.length; i += 1) {
      const leg = MeshBuilder.CreateCylinder(`${primitive.id}-leg-${i}`, {
        height: legHeight,
        diameter: legRadius * 2,
        tessellation: 8,
      }, scene);
      leg.parent = root;
      leg.position.x = legPositions[i].x;
      leg.position.z = legPositions[i].z;
      leg.position.y = legHeight / 2;
      leg.material = material;
    }
    return { root, material };
  }

  // Default: a single box (apple-box / cube / platform / block-*).
  const mesh = MeshBuilder.CreateBox(
    `${primitive.id}-mesh`,
    {
      width: primitive.size.x,
      height: primitive.size.y,
      depth: primitive.size.z,
    },
    scene,
  );
  mesh.parent = root;
  mesh.position.y = primitive.size.y / 2;
  mesh.material = material;
  return { root, material };
}

export class PoseCraftViewportController {
  private readonly canvas: HTMLCanvasElement;

  readonly engine: AbstractEngine;

  readonly scene: Scene;

  readonly camera: ArcRotateCamera;

  readonly status: PoseCraftViewportStatus;

  private readonly figureRigs = new Map<string, FigureRig>();

  private readonly primitiveRigs = new Map<string, PrimitiveRig>();

  /** Gate F — visible on-canvas gizmos. */
  private readonly moveGizmo: AxisGizmo;
  private readonly rotateGizmo: AxisGizmo;
  private readonly poseRing: { root: TransformNode; ring: Mesh; material: StandardMaterial };

  /** Mirror of the canonical figures (id → instance) for pointer picking. */
  private currentFigures = new Map<string, FigureInstance>();

  private disposed = false;

  private gizmoMode: GizmoMode = "move";

  private selectedFigureId: string | null = null;

  private selectedJoint: JointName = "head";

  /** Callback the React layer wires to update canonical state + persist. */
  onManipulate?: (event: ManipulationEvent) => void;

  /** Internal drag state for in-viewport manipulation. */
  private drag: {
    kind: "move" | "rotate" | "pose";
    figureId: string;
    joint?: JointName;
    axis?: "x" | "y" | "z";
    startX: number;
    startY: number;
    startRotationY?: number;
    startRotation?: { x: number; y: number; z: number };
    startPosition?: { x: number; z: number };
    pointerId: number;
  } | null = null;

  private constructor(
    canvas: HTMLCanvasElement,
    engine: AbstractEngine,
    scene: Scene,
    camera: ArcRotateCamera,
    status: PoseCraftViewportStatus,
    moveGizmo: AxisGizmo,
    rotateGizmo: AxisGizmo,
    poseRing: { root: TransformNode; ring: Mesh; material: StandardMaterial },
  ) {
    this.canvas = canvas;
    this.engine = engine;
    this.scene = scene;
    this.camera = camera;
    this.status = status;
    this.moveGizmo = moveGizmo;
    this.rotateGizmo = rotateGizmo;
    this.poseRing = poseRing;
  }

  static async create(canvas: HTMLCanvasElement) {
    let engine: AbstractEngine;
    let renderer: RendererKind = "webgl";
    let detail = "WebGL active";

    if ("gpu" in navigator) {
      try {
        const module = await import("@babylonjs/core/Engines/webgpuEngine");
        const webgpuEngine = new module.WebGPUEngine(canvas, {
          antialias: true,
          adaptToDeviceRatio: true,
        });
        await webgpuEngine.initAsync();
        engine = webgpuEngine;
        renderer = "webgpu";
        detail = "WebGPU active";
      } catch {
        engine = new Engine(canvas, true, {
          preserveDrawingBuffer: true,
          stencil: true,
        });
        detail = "WebGPU unavailable, using WebGL";
      }
    } else {
      engine = new Engine(canvas, true, {
        preserveDrawingBuffer: true,
        stencil: true,
      });
      detail = "WebGPU unavailable, using WebGL";
    }

    const scene = new Scene(engine);
    // Master Program: gray matte stage — neutral, non-distracting, lets the
    // colored staging figures read clearly. Subtle grid + axes remain.
    scene.clearColor = new Color4(0.78, 0.80, 0.83, 1);

    const camera = new ArcRotateCamera(
      "posecraft-camera",
      -Math.PI / 2,
      1.12,
      7.5,
      new Vector3(0, 1.2, 0),
      scene,
    );
    camera.attachControl(canvas, true);
    camera.lowerRadiusLimit = 2.2;
    camera.upperRadiusLimit = 16;
    camera.wheelDeltaPercentage = 0.01;
    camera.panningSensibility = 70;

    const hemi = new HemisphericLight("posecraft-hemi", new Vector3(0.35, 1, 0.2), scene);
    hemi.intensity = 0.95;
    hemi.groundColor = new Color3(0.62, 0.64, 0.67);

    const floorMat = new StandardMaterial("posecraft-floor", scene);
    floorMat.diffuseColor = new Color3(0.74, 0.76, 0.79);
    floorMat.specularColor = new Color3(0.04, 0.04, 0.04);

    const floor = MeshBuilder.CreateGround("posecraft-floor", { width: 16, height: 16 }, scene);
    floor.material = floorMat;
    floor.receiveShadows = false;

    const gridMat = new StandardMaterial("posecraft-grid", scene);
    gridMat.emissiveColor = new Color3(0.58, 0.60, 0.63);

    // Subtle gray grid on the matte stage — major lines slightly darker.
    for (let index = -8; index <= 8; index += 1) {
      const major = index % 4 === 0;
      const line = MeshBuilder.CreateLines(
        `grid-x-${index}`,
        {
          points: [
            new Vector3(index, 0.01, -8),
            new Vector3(index, 0.01, 8),
            new Vector3(-8, 0.01, index),
            new Vector3(8, 0.01, index),
          ],
        },
        scene,
      );
      line.color = major ? new Color3(0.42, 0.44, 0.47) : new Color3(0.6, 0.62, 0.65);
    }

    const axisX = MeshBuilder.CreateLines(
      "axis-x",
      { points: [new Vector3(0, 0.02, 0), new Vector3(2.4, 0.02, 0)] },
      scene,
    );
    axisX.color = new Color3(0.85, 0.25, 0.2);

    const axisY = MeshBuilder.CreateLines(
      "axis-y",
      { points: [new Vector3(0, 0.02, 0), new Vector3(0, 2.4, 0)] },
      scene,
    );
    axisY.color = new Color3(0.2, 0.65, 0.35);

    const axisZ = MeshBuilder.CreateLines(
      "axis-z",
      { points: [new Vector3(0, 0.02, 0), new Vector3(0, 0.02, 2.4)] },
      scene,
    );
    axisZ.color = new Color3(0.18, 0.45, 0.86);

    const controller = new PoseCraftViewportController(canvas, engine, scene, camera, {
      renderer,
      detail,
    }, createMoveGizmo(scene), createRotateGizmo(scene), createPoseRing(scene));

    engine.runRenderLoop(() => {
      if (!controller.disposed) {
        scene.render();
      }
    });
    window.addEventListener("resize", controller.handleResize);
    controller.attachPointerEvents();

    // Expose for Playwright certification (Final Mandatory GO): allows the
    // test harness to read per-figure low-poly human metadata (modelId,
    // jointCount, bodyRegions, legacyBlockModel) without poking the DOM.
    (globalThis as any).__posecraftController = controller;

    return controller;
  }

  setGizmoMode(mode: GizmoMode) {
    this.gizmoMode = mode;
    this.updateHandleVisibility();
    this.updateGizmoPlacement();
  }

  getGizmoMode(): GizmoMode {
    return this.gizmoMode;
  }

  setSelectedFigure(figureId: string | null) {
    this.selectedFigureId = figureId;
    this.updateHandleVisibility();
    this.updateGizmoPlacement();
  }

  /** Final Mandatory GO: expose a figure's low-poly human metadata. */
  getFigureMetadata(figureId: string): BuiltHumanMesh["metadata"] | null {
    const rig = this.figureRigs.get(figureId);
    return rig ? rig.metadata : null;
  }

  /** Final Mandatory GO: list figure ids currently in the scene. */
  getFigureIds(): string[] {
    return Array.from(this.figureRigs.keys());
  }

  /**
   * Gate F — place the active gizmo at the selected figure's root (move/
   * rotate) or at the selected joint (pose ring). Gizmos are hidden when no
   * figure is selected or when the mode does not match.
   */
  private updateGizmoPlacement() {
    const figureId = this.selectedFigureId;
    const rig = figureId ? this.figureRigs.get(figureId) : null;
    const figure = figureId ? this.currentFigures.get(figureId) : null;

    this.moveGizmo.root.setEnabled(this.gizmoMode === "move" && !!rig && !!figure);
    this.rotateGizmo.root.setEnabled(this.gizmoMode === "rotate" && !!rig && !!figure);

    if (rig && figure) {
      // Move/Rotate gizmos sit at the camera target height (≈1.2m) so they
      // project to canvas center, making the axis handles easy to click for
      // real pointer gestures (Gate F).
      this.moveGizmo.root.position.x = figure.position.x;
      this.moveGizmo.root.position.z = figure.position.z;
      this.moveGizmo.root.position.y = 1.2;
      this.rotateGizmo.root.position.x = figure.position.x;
      this.rotateGizmo.root.position.z = figure.position.z;
      this.rotateGizmo.root.position.y = 1.2;
    }

    // Pose ring sits at the selected joint of the selected figure.
    const poseActive = this.gizmoMode === "pose" && !!rig && !!figure;
    if (poseActive) {
      const jointNode = rig!.joints[this.selectedJoint];
      if (jointNode) {
        this.poseRing.root.setEnabled(true);
        this.poseRing.root.parent = jointNode;
        this.poseRing.root.position.set(0, 0, 0);
      } else {
        this.poseRing.root.setEnabled(false);
      }
    } else {
      this.poseRing.root.setEnabled(false);
      this.poseRing.root.parent = null;
    }
  }

  private updateHandleVisibility() {
    const poseMode = this.gizmoMode === "pose";
    for (const [id, rig] of this.figureRigs.entries()) {
      const selected = id === this.selectedFigureId;
      for (const handle of Object.values(rig.handles)) {
        handle.setEnabled(poseMode && selected);
      }
    }
  }

  private attachPointerEvents() {
    this.scene.onPointerObservable.add((info) => {
      if (this.disposed) return;
      const evt = info.event as PointerEvent;
      if (info.type === PointerEventTypes.POINTERDOWN) {
        this.handlePointerDown(evt);
      } else if (info.type === PointerEventTypes.POINTERMOVE) {
        this.handlePointerMove(evt);
      } else if (info.type === PointerEventTypes.POINTERUP) {
        this.handlePointerUp(evt);
      }
    });
  }

  private pointerCanvasCoords(evt: PointerEvent): { x: number; y: number } {
    const rect = this.canvas.getBoundingClientRect();
    const cssX = evt.clientX - rect.left;
    const cssY = evt.clientY - rect.top;
    const sx = rect.width > 0 ? cssX * (this.canvas.width / rect.width) : cssX;
    const sy = rect.height > 0 ? cssY * (this.canvas.height / rect.height) : cssY;
    return { x: sx, y: sy };
  }

  private pickFigureId(px: number, py: number): string | null {
    const pick = this.scene.pick(px, py, (mesh) => {
      const name = mesh?.name ?? "";
      return name.startsWith("posecraft-") === false && !name.includes("-handle-") && !name.startsWith("grid-") && !name.startsWith("axis-") && !name.includes("gizmo-");
    });
    if (!pick?.hit || !pick.pickedMesh) return null;
    const name = pick.pickedMesh.name;
    // Final Mandatory GO: body meshes are named `${figureId}-body-${region}` (and
    // thumbs `${figureId}-body-${region}-thumb`). Resolve the figure id from
    // that prefix; fall back to the legacy mesh-suffix list for older rigs.
    const bodyMatch = name.match(/^(.+)-body-/);
    if (bodyMatch) return bodyMatch[1]!;
    const match = name.match(/^([a-zA-Z0-9_-]+?)-(root|pelvisBox|spineBox|chestBox|neckCyl|headBall|leftUpperArm|leftLowerArm|leftHand|rightUpperArm|rightLowerArm|rightHand|leftUpperLeg|leftLowerLeg|leftFoot|rightUpperLeg|rightLowerLeg|rightFoot|ring|handle-)/);
    if (!match) return null;
    return match[1]!;
  }

  /**
   * Final Mandatory GO: resolve a body-mesh click to the pose joint for the
   * region that was clicked (chest → chest, leftUpperArm → leftShoulder, …).
   * Returns null if the picked mesh is not a body-region mesh.
   */
  private pickBodyJoint(px: number, py: number): { figureId: string; joint: JointName } | null {
    const pick = this.scene.pick(px, py, (mesh) => {
      const name = mesh?.name ?? "";
      return name.includes("-body-");
    });
    if (!pick?.hit || !pick.pickedMesh) return null;
    const name = pick.pickedMesh.name;
    const figureMatch = name.match(/^(.+)-body-/);
    const region = regionFromMeshName(name);
    if (!figureMatch || !region) return null;
    const joint = REGION_TO_JOINT[region];
    return { figureId: figureMatch[1]!, joint };
  }

  private pickJointHandle(px: number, py: number): { figureId: string; joint: JointName } | null {
    const pick = this.scene.pick(px, py, (mesh) => {
      const name = mesh?.name ?? "";
      return name.includes("-handle-");
    });
    if (!pick?.hit || !pick.pickedMesh) return null;
    const name = pick.pickedMesh.name;
    const m = name.match(/^(.+)-handle-([a-zA-Z]+)$/);
    if (!m) return null;
    return { figureId: m[1]!, joint: m[2] as JointName };
  }

  /**
   * Gate F — pick a visible gizmo handle (move axis arrow or rotate ring or
   * pose ring). Returns the gizmo kind and axis so the drag can be constrained
   * to the picked handle. Names: posecraft-gizmo-move-{x|y|z},
   * posecraft-gizmo-rotate-{x|y|z}, posecraft-gizmo-pose-ring.
   */
  private pickGizmoHandle(px: number, py: number): { kind: "move" | "rotate" | "pose"; axis?: "x" | "y" | "z" } | null {
    const pick = this.scene.pick(px, py, (mesh) => {
      const name = mesh?.name ?? "";
      return mesh.isEnabled(true) && name.startsWith("posecraft-gizmo-");
    });
    if (!pick?.hit || !pick.pickedMesh) return null;
    const name = pick.pickedMesh.name;
    if (name.startsWith("posecraft-gizmo-move-")) {
      const axis = name.slice("posecraft-gizmo-move-".length).replace(/-shaft$/, "").replace(/-tip$/, "") as "x" | "y" | "z";
      return { kind: "move", axis };
    }
    if (name.startsWith("posecraft-gizmo-rotate-")) {
      const axis = name.slice("posecraft-gizmo-rotate-".length) as "x" | "y" | "z";
      return { kind: "rotate", axis };
    }
    if (name.startsWith("posecraft-gizmo-pose-ring")) {
      return { kind: "pose" };
    }
    return null;
  }

  private handlePointerDown(evt: PointerEvent) {
    // Gate F — first try a visible gizmo handle (move axis / rotate ring /
    // pose ring). The drag is constrained to the picked handle's axis so
    // "mouse down on X-axis handle → drag → root X changes" is literally true.
    const { x: px, y: py } = this.pointerCanvasCoords(evt);
    const gizmo = this.pickGizmoHandle(px, py);
    (globalThis as any).__pcDown = { gizmo, mode: this.gizmoMode, moveEnabled: this.moveGizmo.root.isEnabled(), rotateEnabled: this.rotateGizmo.root.isEnabled(), hasSelected: !!this.selectedFigureId, px: Math.round(px), py: Math.round(py), clientX: Math.round(evt.clientX) };
    if (gizmo && this.selectedFigureId) {
      const rig = this.figureRigs.get(this.selectedFigureId);
      const figure = this.currentFigures.get(this.selectedFigureId);
      if (rig && figure) {
        if (gizmo.kind === "move" && gizmo.axis) {
          this.drag = {
            kind: "move",
            figureId: this.selectedFigureId,
            axis: gizmo.axis,
            startX: evt.clientX,
            startY: evt.clientY,
            startPosition: { x: figure.position.x, z: figure.position.z },
            pointerId: evt.pointerId,
          };
          this.camera.detachControl();
          evt.preventDefault();
          return;
        }
        if (gizmo.kind === "rotate" && gizmo.axis) {
          this.drag = {
            kind: "rotate",
            figureId: this.selectedFigureId,
            axis: gizmo.axis,
            startX: evt.clientX,
            startY: evt.clientY,
            startRotationY: figure.rotationY,
            pointerId: evt.pointerId,
          };
          this.camera.detachControl();
          evt.preventDefault();
          return;
        }
        if (gizmo.kind === "pose") {
          const joint = this.selectedJoint;
          const r = figure.pose[joint] ?? { x: 0, y: 0, z: 0 };
          this.drag = {
            kind: "pose",
            figureId: this.selectedFigureId,
            joint,
            startX: evt.clientX,
            startY: evt.clientY,
            startRotation: { x: r.x, y: r.y, z: r.z },
            pointerId: evt.pointerId,
          };
          this.camera.detachControl();
          evt.preventDefault();
          return;
        }
      }
    }

    // Pose mode: try to pick a joint handle first (selects the joint).
    if (this.gizmoMode === "pose") {
      const handle = this.pickJointHandle(px, py);
      if (handle && this.selectedFigureId === handle.figureId) {
        const rig = this.figureRigs.get(handle.figureId);
        const figure = this.currentFigures?.get(handle.figureId);
        if (rig && figure) {
          this.selectedJoint = handle.joint;
          this.onManipulate?.({ kind: "select", figureId: handle.figureId });
          const r = figure.pose[handle.joint] ?? { x: 0, y: 0, z: 0 };
          this.drag = {
            kind: "pose",
            figureId: handle.figureId,
            joint: handle.joint,
            startX: evt.clientX,
            startY: evt.clientY,
            startRotation: { x: r.x, y: r.y, z: r.z },
            pointerId: evt.pointerId,
          };
          this.updateGizmoPlacement();
          this.camera.detachControl();
          evt.preventDefault();
        }
        return;
      }
    }
    // Otherwise: pick a figure body to select. In pose mode, first try to
    // resolve the body region under the cursor to a pose joint (chest → chest,
    // leftUpperArm → leftShoulder, …) so clicking a body part selects the
    // intended joint. Then begin a move/rotate/pose drag on the body.
    const bodyJoint = (this.gizmoMode === "pose") ? this.pickBodyJoint(px, py) : null;
    const figureId = bodyJoint?.figureId ?? this.pickFigureId(px, py);
    if (figureId) {
      this.selectedFigureId = figureId;
      if (bodyJoint && bodyJoint.figureId === figureId) {
        this.selectedJoint = bodyJoint.joint;
      }
      this.updateHandleVisibility();
      this.updateGizmoPlacement();
      this.onManipulate?.({ kind: "select", figureId });
      const figure = this.currentFigures?.get(figureId);
      if (figure && this.gizmoMode === "pose") {
        const joint: JointName = (this.selectedJoint && figure.pose[this.selectedJoint] !== undefined) ? this.selectedJoint : "spine";
        this.selectedJoint = joint;
        const r = figure.pose[joint] ?? { x: 0, y: 0, z: 0 };
        this.drag = {
          kind: "pose",
          figureId,
          joint,
          startX: evt.clientX,
          startY: evt.clientY,
          startRotation: { x: r.x, y: r.y, z: r.z },
          pointerId: evt.pointerId,
        };
        this.updateGizmoPlacement();
        this.camera.detachControl();
        evt.preventDefault();
      } else if (figure && (this.gizmoMode === "move" || this.gizmoMode === "rotate")) {
        this.drag = {
          kind: this.gizmoMode,
          figureId,
          axis: this.gizmoMode === "move" ? "x" : "y",
          startX: evt.clientX,
          startY: evt.clientY,
          startRotationY: figure.rotationY,
          startPosition: { x: figure.position.x, z: figure.position.z },
          pointerId: evt.pointerId,
        };
        this.camera.detachControl();
        evt.preventDefault();
      }
    }
  }

  private handlePointerMove(evt: PointerEvent) {
    if (!this.drag) return;
    (globalThis as any).__pcMoveCount = ((globalThis as any).__pcMoveCount ?? 0) + 1;
    const rig = this.figureRigs.get(this.drag.figureId);
    const figure = this.currentFigures?.get(this.drag.figureId);
    if (!rig || !figure) return;
    const dx = evt.clientX - this.drag.startX;
    const dy = evt.clientY - this.drag.startY;
    if (this.drag.kind === "move") {
      const scale = 0.012;
      const axis = this.drag.axis ?? "x";
      const start = this.drag.startPosition ?? { x: figure.position.x, z: figure.position.z };
      if (axis === "x") {
        rig.root.position.x = start.x + dx * scale;
      } else if (axis === "z") {
        rig.root.position.z = start.z + dy * scale;
      } else {
        // Y axis — figures stay snapped to the floor; allow a small lift.
        rig.root.position.y = Math.max(0, -dy * scale);
      }
    } else if (this.drag.kind === "rotate") {
      const axis = this.drag.axis ?? "y";
      if (axis === "y") {
        const deg = (this.drag.startRotationY ?? 0) + dx * 0.5;
        rig.root.rotation = new Vector3(0, degreesToRadians(deg), 0);
      } else if (axis === "x") {
        // Tilt forward/back — applied to spine for a readable pose.
        const deg = dy * 0.5;
        rig.joints.spine.rotation.x = degreesToRadians(deg);
      } else {
        const deg = dx * 0.5;
        rig.joints.spine.rotation.z = degreesToRadians(deg);
      }
    } else if (this.drag.kind === "pose" && this.drag.joint && this.drag.startRotation) {
      const base = this.drag.startRotation;
      const x = Math.round(base.x + dy * 0.6);
      const z = Math.round(base.z + dx * 0.6);
      const y = evt.shiftKey ? Math.round(base.y + dx * 0.6) : base.y;
      const jointNode = rig.joints[this.drag.joint];
      jointNode.rotation.x = degreesToRadians(x);
      jointNode.rotation.y = degreesToRadians(y);
      jointNode.rotation.z = degreesToRadians(z);
    }
  }

  private handlePointerUp(evt: PointerEvent) {
    if (!this.drag) return;
    const drag = this.drag;
    this.drag = null;
    (globalThis as any).__pcUp = { kind: drag.kind, axis: drag.axis, rootX: drag.figureId ? this.figureRigs.get(drag.figureId)?.root.position.x : null };
    this.camera.attachControl(this.canvas, true);
    const figure = this.currentFigures?.get(drag.figureId);
    if (!figure) return;
    const rig = this.figureRigs.get(drag.figureId);
    if (!rig) return;
    if (drag.kind === "move") {
      const x = Number(rig.root.position.x.toFixed(2));
      const z = Number(rig.root.position.z.toFixed(2));
      this.onManipulate?.({ kind: "move", figureId: drag.figureId, position: { x, z } });
    } else if (drag.kind === "rotate") {
      const axis = drag.axis ?? "y";
      if (axis === "y") {
        const deg = Math.round((drag.startRotationY ?? 0) + (evt.clientX - drag.startX) * 0.5);
        this.onManipulate?.({ kind: "rotate", figureId: drag.figureId, rotationY: deg });
      }
      // X/Z ring tilts are applied to the spine as a pose tweak; emit a pose
      // event so the canonical state stays in sync.
      if (axis !== "y") {
        const base = figure.pose.spine ?? { x: 0, y: 0, z: 0 };
        const x = axis === "x" ? Math.round(base.x + (evt.clientY - drag.startY) * 0.5) : base.x;
        const z = axis === "z" ? Math.round(base.z + (evt.clientX - drag.startX) * 0.5) : base.z;
        this.onManipulate?.({ kind: "pose", figureId: drag.figureId, joint: "spine", rotation: { x, y: base.y, z } });
      }
    } else if (drag.kind === "pose" && drag.joint && drag.startRotation) {
      const base = drag.startRotation;
      const x = Math.round(base.x + (evt.clientY - drag.startY) * 0.6);
      const z = Math.round(base.z + (evt.clientX - drag.startX) * 0.6);
      const y = evt.shiftKey ? Math.round(base.y + (evt.clientX - drag.startX) * 0.6) : base.y;
      this.onManipulate?.({
        kind: "pose",
        figureId: drag.figureId,
        joint: drag.joint,
        rotation: { x, y, z },
      });
    }
  }

  private readonly handleResize = () => {
    if (!this.disposed) {
      this.engine.resize();
    }
  };

  sync(sceneDoc: PoseCraftScene, selectedFigureId: string | null) {
    this.selectedFigureId = selectedFigureId;
    this.selectedJoint = sceneDoc.selectedJoint;
    this.currentFigures = new Map(sceneDoc.figures.map((f) => [f.id, f]));
    this.camera.alpha = sceneDoc.camera.alpha;
    this.camera.beta = sceneDoc.camera.beta;
    this.camera.radius = sceneDoc.camera.radius;
    this.camera.target.copyFrom(
      new Vector3(sceneDoc.camera.target.x, sceneDoc.camera.target.y, sceneDoc.camera.target.z),
    );
    this.camera.fov = lensToFov(sceneDoc.camera.lensMm);

    const figureIds = new Set(sceneDoc.figures.map((figure) => figure.id));
    for (const [id, rig] of this.figureRigs.entries()) {
      if (!figureIds.has(id)) {
        rig.root.dispose(false, true);
        this.figureRigs.delete(id);
      }
    }

    for (const figure of sceneDoc.figures) {
      let rig = this.figureRigs.get(figure.id);
      if (!rig) {
        rig = createFigureRig(this.scene, figure);
        this.figureRigs.set(figure.id, rig);
      }
      const color = colorFromHex(getColorSpec(figure.colorId).hex);
      rig.material.diffuseColor = color;
      rig.material.emissiveColor = color.scale(0.08);
      rig.root.position.x = figure.position.x;
      rig.root.position.z = figure.position.z;
      rig.root.scaling.setAll(figure.scale);
      rig.root.rotation = new Vector3(0, degreesToRadians(figure.rotationY), 0);
      rig.selectionRing.setEnabled(selectedFigureId === figure.id);
      for (const [joint, jointNode] of Object.entries(rig.joints) as [JointName, TransformNode][]) {
        const rotation = figure.pose[joint];
        jointNode.rotation.x = degreesToRadians(rotation.x);
        jointNode.rotation.y = degreesToRadians(rotation.y);
        jointNode.rotation.z = degreesToRadians(rotation.z);
      }
    }
    this.updateHandleVisibility();

    const primitiveIds = new Set(sceneDoc.primitives.map((primitive) => primitive.id));
    for (const [id, rig] of this.primitiveRigs.entries()) {
      if (!primitiveIds.has(id)) {
        rig.root.dispose(false, true);
        this.primitiveRigs.delete(id);
      }
    }

    for (const primitive of sceneDoc.primitives) {
      let rig = this.primitiveRigs.get(primitive.id);
      if (!rig) {
        rig = createPrimitiveRig(this.scene, primitive);
        this.primitiveRigs.set(primitive.id, rig);
      }
      rig.root.setEnabled(sceneDoc.stage.showPrimitives);
      rig.root.position.x = primitive.position.x;
      rig.root.position.z = primitive.position.z;
      rig.root.rotation.y = degreesToRadians(primitive.rotationY ?? 0);
      const s = primitive.scale ?? 1;
      rig.root.scaling.set(s, s, s);
      rig.material.diffuseColor = colorFromHex(primitive.color);
    }
    this.updateGizmoPlacement();
  }

  readCameraState() {
    return {
      alpha: this.camera.alpha,
      beta: this.camera.beta,
      radius: this.camera.radius,
      target: {
        x: Number(this.camera.target.x.toFixed(3)),
        y: Number(this.camera.target.y.toFixed(3)),
        z: Number(this.camera.target.z.toFixed(3)),
      },
    };
  }

  /**
   * Co-Director scene labels — project world positions to canvas CSS pixels
   * for floating HTML labels (pointer-events: none). Hidden when showLabels
   * is false; clean snapshot exports omit these DOM labels automatically.
   */
  getLabelScreenPositions(sceneDoc: PoseCraftScene): Array<{
    id: string;
    label: string;
    x: number;
    y: number;
    selected: boolean;
  }> {
    if (!sceneDoc.stage.showLabels) return [];
    const engine = this.scene.getEngine();
    const w = engine.getRenderWidth();
    const h = engine.getRenderHeight();
    const canvasW = this.canvas.clientWidth || w;
    const canvasH = this.canvas.clientHeight || h;
    const viewport = this.camera.viewport.toGlobal(w, h);
    const transform = this.scene.getTransformMatrix();
    const identity = Matrix.Identity();
    const out: Array<{ id: string; label: string; x: number; y: number; selected: boolean }> = [];

    const project = (world: Vector3) => {
      const p = Vector3.Project(world, identity, transform, viewport);
      return {
        x: p.x * (canvasW / w),
        y: p.y * (canvasH / h),
      };
    };

    for (const figure of sceneDoc.figures) {
      if (figure.visible === false) continue;
      const rig = this.figureRigs.get(figure.id);
      if (!rig) continue;
      const world = rig.root.getAbsolutePosition().clone();
      world.y += 1.85 * (figure.scale || 1);
      const { x, y } = project(world);
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      out.push({
        id: figure.id,
        label: figure.name,
        x,
        y,
        selected: sceneDoc.selectedFigureId === figure.id,
      });
    }
    for (const primitive of sceneDoc.primitives) {
      if (primitive.visible === false) continue;
      const rig = this.primitiveRigs.get(primitive.id);
      if (!rig) continue;
      const world = rig.root.getAbsolutePosition().clone();
      world.y += (primitive.size?.y ?? 0.5) + 0.15;
      const { x, y } = project(world);
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      out.push({
        id: primitive.id,
        label: primitive.name,
        x,
        y,
        selected: sceneDoc.selectedPrimitiveId === primitive.id,
      });
    }
    return out;
  }

  captureSnapshot() {
    this.scene.render();
    return this.canvas.toDataURL("image/png");
  }

  /**
   * PoseCraft Snapshot — capture a CLEAN PNG of the exact camera composition
   * currently shown in the viewport, with all gizmos / joint handles / selection
   * outlines / floating labels / safe-margin & rule-of-thirds guides hidden so
   * the handoff image is a pure staging frame. The viewport state is restored
   * exactly after capture so the creator's working view is unchanged.
   *
   * This is NOT a scene save. Scene autosave/flush stays independent and never
   * PNG-captures. Returns a PNG data URL ready for upload to the project Library.
   */
  captureCleanSnapshot(): string {
    // Snapshot the visibility state of everything we hide so we can restore it
    // exactly — even if a render callback or pointer event fires mid-capture.
    const prevMoveEnabled = this.moveGizmo.root.isEnabled(false);
    const prevRotateEnabled = this.rotateGizmo.root.isEnabled(false);
    const prevPoseEnabled = this.poseRing.root.isEnabled(false);
    const prevHandleVisibility = new Map<string, boolean>();
    for (const [id, rig] of this.figureRigs.entries()) {
      for (const [joint, handle] of Object.entries(rig.handles) as [JointName, Mesh][]) {
        prevHandleVisibility.set(`${id}:${joint}`, handle.isEnabled(false));
      }
      // Selection outline ring — hide it for a clean frame.
      prevHandleVisibility.set(`${id}:__selectionRing`, rig.selectionRing.isEnabled(false));
      rig.selectionRing.setEnabled(false);
    }

    // Hide all gizmos / handles / pose ring.
    this.moveGizmo.root.setEnabled(false);
    this.rotateGizmo.root.setEnabled(false);
    this.poseRing.root.setEnabled(false);
    for (const rig of this.figureRigs.values()) {
      for (const handle of Object.values(rig.handles)) {
        handle.setEnabled(false);
      }
    }

    // Camera guides (safe / center / thirds) are DOM overlays and floating
    // labels are HTML — the React capture handler hides those during capture
    // via a transient flag. Here we only clean the 3D scene.

    // Force a fresh render with the clean state, then capture.
    this.scene.render();
    const dataUrl = this.canvas.toDataURL("image/png");

    // Restore exactly.
    this.moveGizmo.root.setEnabled(prevMoveEnabled);
    this.rotateGizmo.root.setEnabled(prevRotateEnabled);
    this.poseRing.root.setEnabled(prevPoseEnabled);
    for (const [id, rig] of this.figureRigs.entries()) {
      const prevRing = prevHandleVisibility.get(`${id}:__selectionRing`);
      rig.selectionRing.setEnabled(Boolean(prevRing));
      for (const [joint, handle] of Object.entries(rig.handles) as [JointName, Mesh][]) {
        const prev = prevHandleVisibility.get(`${id}:${joint}`);
        handle.setEnabled(Boolean(prev));
      }
    }
    this.updateHandleVisibility();
    this.updateGizmoPlacement();
    this.scene.render();
    return dataUrl;
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    window.removeEventListener("resize", this.handleResize);
    this.engine.stopRenderLoop();
    this.scene.dispose();
    this.engine.dispose();
  }
}
