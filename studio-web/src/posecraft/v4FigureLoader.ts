/**
 * PoseCraft v4 Fable GLB load + bind.
 *
 * Visible regions parent to the existing 17-joint TransformNode rig.
 * No skinning. No procedural human fallback.
 */
import "@babylonjs/loaders/glTF";
import {
  AssetContainer,
  Color3,
  Mesh,
  MeshBuilder,
  PBRMaterial,
  Scene,
  LoadAssetContainerAsync,
  StandardMaterial,
  TransformNode,
  type AbstractMesh,
  type Material,
} from "@babylonjs/core";
import { BODY_REGIONS, REGION_TO_JOINT, type BodyRegion } from "./humanMeshBuilder";
import { V4_REGION_BIND_ROTATION_Z } from "./v4RestJoints";
import type { ArchetypeId, JointName } from "./types";
import { getHumanModelId } from "./humanMeshBuilder";

export type VisualState = "LOADING" | "READY" | "ERROR" | "DISPOSED";

export const V4_REQUIRED_REGIONS: readonly BodyRegion[] = BODY_REGIONS;

const containerCache = new Map<string, Promise<AssetContainer>>();
let containerFetchCount = 0;

export function getV4ContainerFetchCount(): number {
  return containerFetchCount;
}

export function resetV4ContainerCacheForTests(): void {
  containerCache.clear();
  containerFetchCount = 0;
}

export function v4RuntimePath(modelId: string): string {
  return `/posecraft/figures/${modelId}.glb`;
}

export function v4AssetSource(modelId: string): string {
  return v4RuntimePath(modelId);
}

function findNamed(root: TransformNode | AbstractMesh, name: string): TransformNode | AbstractMesh | null {
  if (root.name === name) return root;
  for (const child of root.getChildren()) {
    const hit = findNamed(child as TransformNode, name);
    if (hit) return hit;
  }
  return null;
}

export function collectNamedRegions(figureRoot: TransformNode | AbstractMesh): Map<BodyRegion, AbstractMesh> {
  const found = new Map<BodyRegion, AbstractMesh>();
  for (const region of V4_REQUIRED_REGIONS) {
    const node = findNamed(figureRoot, region);
    if (node && (node as AbstractMesh).getClassName?.().includes("Mesh")) {
      found.set(region, node as AbstractMesh);
    } else if (node) {
      const meshChild = node.getChildMeshes(false)[0];
      if (meshChild) found.set(region, meshChild);
    }
  }
  return found;
}

export function missingV4Regions(found: Map<BodyRegion, AbstractMesh>): BodyRegion[] {
  return V4_REQUIRED_REGIONS.filter((region) => !found.has(region));
}

function sourceRegionMeshes(container: AssetContainer): Map<BodyRegion, AbstractMesh> {
  const found = new Map<BodyRegion, AbstractMesh>();
  const candidates = [...container.meshes, ...container.transformNodes];
  for (const region of V4_REQUIRED_REGIONS) {
    const node = candidates.find((entry) => entry.name === region);
    if (node && (node as AbstractMesh).getTotalVertices?.() > 0) {
      found.set(region, node as AbstractMesh);
      continue;
    }
    if (node) {
      const meshChild = node.getChildMeshes?.(false)?.[0];
      if (meshChild) found.set(region, meshChild);
    }
  }
  return found;
}

async function loadContainer(scene: Scene, modelId: string): Promise<AssetContainer> {
  const existing = containerCache.get(modelId);
  if (existing) return existing;
  containerFetchCount += 1;
  const url = v4RuntimePath(modelId);
  const pending = LoadAssetContainerAsync(url, scene).then((container) => {
    const figure = container.transformNodes.find((n) => n.name === "Figure")
      ?? container.meshes.find((m) => m.name === "Figure");
    if (!figure) {
      throw new Error(`v4 GLB ${modelId} is missing the Figure root`);
    }
    const found = sourceRegionMeshes(container);
    const missing = missingV4Regions(found);
    if (missing.length) {
      throw new Error(`v4 GLB ${modelId} is missing regions: ${missing.join(", ")}`);
    }
    if (container.skeletons.length > 0 || container.animationGroups.length > 0) {
      throw new Error(`v4 GLB ${modelId} must not contain skins or animation`);
    }
    return container;
  });
  containerCache.set(modelId, pending);
  try {
    return await pending;
  } catch (error) {
    containerCache.delete(modelId);
    throw error;
  }
}

export type V4AttachTarget = {
  figureId: string;
  archetypeId: ArchetypeId;
  loadToken: number;
  visualState: VisualState;
  joints: Record<JointName, TransformNode>;
  bodyMeshes: Mesh[];
};

function tintMaterial(material: Material | null, tint: Color3): void {
  if (!material) return;
  if (material instanceof PBRMaterial) {
    const base = material.albedoColor ?? new Color3(0.55, 0.55, 0.58);
    material.albedoColor = Color3.Lerp(base, tint, 0.42);
    return;
  }
  if (material instanceof StandardMaterial) {
    material.diffuseColor = Color3.Lerp(material.diffuseColor, tint, 0.42);
  }
}

export async function attachV4Figure(options: {
  scene: Scene;
  target: V4AttachTarget;
  expectedToken: number;
  tint: Color3;
  isCurrent: () => boolean;
}): Promise<{ triangleCount: number; modelId: string; assetSource: string } | null> {
  const { scene, target, tint, isCurrent } = options;
  if (!isCurrent()) return null;
  const modelId = getHumanModelId(target.archetypeId);
  const container = await loadContainer(scene, modelId);
  if (!isCurrent()) {
    return null;
  }
  const found = sourceRegionMeshes(container);
  const missing = missingV4Regions(found);
  if (missing.length) {
    throw new Error(`v4 GLB ${modelId} is missing regions: ${missing.join(", ")}`);
  }

  let triangleCount = 0;
  for (const region of V4_REQUIRED_REGIONS) {
    const source = found.get(region)! as Mesh;
    const joint = target.joints[REGION_TO_JOINT[region]];
    const mesh = source.clone(`${target.figureId}-body-${region}`, joint);
    if (!mesh) throw new Error(`v4 clone failed for ${modelId} ${region}`);
    // Binding law: the clone must carry ONLY the static bind rotation. The
    // glTF loader leaves a rotationQuaternion on nodes (which makes Euler
    // .rotation writes silent no-ops) and the clone leaves Babylon's __root__
    // handedness transform behind, so we null the quaternion, bind in raw
    // authored coordinates (left = −X, matching the rig), and rotate the
    // T-pose arm-chain geometry onto the hanging skeleton.
    mesh.rotationQuaternion = null;
    mesh.position.set(0, 0, 0);
    mesh.rotation.set(0, 0, V4_REGION_BIND_ROTATION_Z[region]);
    mesh.scaling.setAll(1);
    mesh.isPickable = true;
    mesh.setEnabled(true);
    mesh.metadata = { figureId: target.figureId, region, kind: "body" };
    if (mesh.material) {
      mesh.material = mesh.material.clone(`${target.figureId}-mat-${region}`);
      // Without the __root__ negative-determinant transform the loader's
      // side-orientation assumption inverts; disabling culling renders (and
      // ray-picks) both faces so the mannequin can never appear inside-out.
      if (mesh.material) mesh.material.backFaceCulling = false;
      tintMaterial(mesh.material, tint);
    }
    attachPickCollider(scene, mesh, target.figureId, region);
    const indices = mesh.getIndices?.();
    triangleCount += indices ? Math.floor(indices.length / 3) : 0;
    target.bodyMeshes.push(mesh);
  }
  return { triangleCount, modelId, assetSource: v4AssetSource(modelId) };
}

const TORSO_REGIONS: ReadonlySet<BodyRegion> = new Set(["head", "neck", "chest", "spine", "pelvis"]);

/**
 * Invisible, slightly enlarged pick collider per region. Picking against
 * triangle-exact render meshes made thin limbs nearly unclickable; the
 * collider is a box around the region's local bounds, parented to the visible
 * mesh (so it follows the bind rotation and every joint rotation), invisible
 * but ray-pickable through the engine's explicit pick predicates.
 */
export function attachPickCollider(scene: Scene, mesh: Mesh, figureId: string, region: BodyRegion): Mesh {
  const bounds = mesh.getBoundingInfo().boundingBox;
  const scaleFactor = TORSO_REGIONS.has(region) ? 1.08 : 1.3;
  const pad = TORSO_REGIONS.has(region) ? 0.005 : 0.02;
  const width = Math.max(0.04, bounds.extendSize.x * 2 * scaleFactor + pad);
  const height = Math.max(0.04, bounds.extendSize.y * 2 * scaleFactor + pad);
  const depth = Math.max(0.04, bounds.extendSize.z * 2 * scaleFactor + pad);
  const collider = MeshBuilder.CreateBox(`${figureId}-pick-${region}`, { width, height, depth }, scene);
  collider.parent = mesh;
  collider.position.copyFrom(bounds.center);
  collider.isVisible = false;
  collider.isPickable = true;
  collider.metadata = { figureId, region, kind: "collider" };
  return collider;
}

export function highlightRegionMeshes(meshes: Mesh[], region: BodyRegion | null): void {
  for (const mesh of meshes) {
    const meshRegion = mesh.metadata?.region as BodyRegion | undefined;
    const material = mesh.material;
    if (!(material instanceof StandardMaterial) && !(material instanceof PBRMaterial)) continue;
    const selected = region !== null && meshRegion === region;
    if (material instanceof PBRMaterial) {
      material.emissiveColor = selected ? new Color3(0.28, 0.42, 0.55) : new Color3(0.02, 0.02, 0.03);
      continue;
    }
    material.emissiveColor = selected ? new Color3(0.35, 0.55, 0.72) : material.diffuseColor.scale(0.08);
  }
}
