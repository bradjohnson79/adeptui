/**
 * Co-Director Scene Labels — semantic packaging for inspect / Image Gen / Storyboard.
 *
 * Creator-facing `name` is the scene label. Permanent `id` never changes on rename.
 */

import { getArchetypeSpec } from "./state";
import type {
  BlockingPrimitive,
  FigureInstance,
  FigureRole,
  PoseCraftDocument,
  PoseCraftScene,
} from "./types";

export type PoseCraftSemanticObject = {
  id: string;
  label: string;
  type: string;
  role?: FigureRole;
  transform: {
    position: { x: number; y: number; z: number };
    rotationY: number;
    scale: number;
  };
  visible: boolean;
  locked: boolean;
};

export type PoseCraftSemanticFigure = PoseCraftSemanticObject & {
  characterId?: string | null;
  archetypeId?: string;
  modelId?: string;
  customAssetId?: string | null;
  poseId?: string | null;
  poseLabel?: string | null;
  poseSummary?: string;
  eyelineTargetId?: string | null;
  creatorModified: boolean;
  colorId?: string;
};

export type PoseCraftSemanticPrimitive = PoseCraftSemanticObject & {
  furnitureKind: string;
};

function figureType(figure: FigureInstance): string {
  if (figure.kind === "custom") return "custom-figure";
  return figure.archetypeId;
}

function poseSummary(figure: FigureInstance): string | undefined {
  if (figure.kind === "custom") return undefined;
  if (figure.poseLabel) return figure.poseLabel;
  if (figure.poseId) return figure.poseId;
  return "Neutral";
}

export function toSemanticFigure(
  figure: FigureInstance,
  creatorModified = false,
): PoseCraftSemanticFigure {
  const isCustom = figure.kind === "custom";
  const spec = getArchetypeSpec(figure.archetypeId);
  return {
    id: figure.id,
    label: figure.name,
    type: figureType(figure),
    role: figure.role ?? "unspecified",
    transform: {
      position: { x: figure.position.x, y: 0, z: figure.position.z },
      rotationY: figure.rotationY,
      scale: figure.scale,
    },
    visible: figure.visible !== false,
    locked: Boolean(figure.locked),
    characterId: figure.characterId ?? null,
    archetypeId: figure.archetypeId,
    modelId: isCustom ? "custom-mesh" : spec.modelId,
    customAssetId: isCustom ? figure.customAssetId : undefined,
    poseId: figure.poseId ?? null,
    poseLabel: figure.poseLabel ?? null,
    poseSummary: poseSummary(figure),
    eyelineTargetId: figure.eyelineTargetId ?? null,
    creatorModified,
    colorId: figure.colorId,
  };
}

export function toSemanticPrimitive(primitive: BlockingPrimitive): PoseCraftSemanticPrimitive {
  return {
    id: primitive.id,
    label: primitive.name,
    type: primitive.kind,
    transform: {
      position: { x: primitive.position.x, y: 0, z: primitive.position.z },
      rotationY: primitive.rotationY ?? 0,
      scale: primitive.scale ?? 1,
    },
    visible: primitive.visible !== false,
    locked: Boolean(primitive.locked),
    furnitureKind: primitive.kind,
  };
}

/** Human-readable scene summary for Co-Director (uses labels, not colors). */
export function buildSemanticSceneSummary(scene: PoseCraftScene): string {
  const lines: string[] = [`Scene: ${scene.name}`];
  for (const figure of scene.figures) {
    if (figure.visible === false) continue;
    const role = figure.role && figure.role !== "unspecified" ? ` (${figure.role})` : "";
    const pose = poseSummary(figure);
    const type = figure.kind === "custom" ? "Custom Figure" : getArchetypeSpec(figure.archetypeId).label;
    lines.push(`${figure.name}${role} — ${type}${pose ? ` — ${pose}` : ""}`);
  }
  for (const primitive of scene.primitives) {
    if (primitive.visible === false) continue;
    lines.push(`${primitive.name} — ${primitive.kind}`);
  }
  return lines.join("\n");
}

/**
 * Package consumed by Image Generation / Storyboard / Co-Director inspect.
 * Includes permanent IDs + editable labels + roles + transforms.
 */
export function buildSemanticPackage(document: PoseCraftDocument) {
  const scene = document.currentScene;
  const creatorModified = Boolean((scene as { creatorModified?: boolean }).creatorModified);
  return {
    sceneName: scene.name,
    revision: scene.revision,
    updatedAt: scene.updatedAt,
    notes: scene.notes,
    summary: buildSemanticSceneSummary(scene),
    figures: scene.figures.map((figure) => toSemanticFigure(figure, creatorModified)),
    objects: scene.primitives.map(toSemanticPrimitive),
    camera: {
      lensMm: scene.camera.lensMm,
      aspect: scene.camera.aspect,
      guides: scene.camera.guides,
      alpha: scene.camera.alpha,
      beta: scene.camera.beta,
      radius: scene.camera.radius,
      target: scene.camera.target,
    },
  };
}
