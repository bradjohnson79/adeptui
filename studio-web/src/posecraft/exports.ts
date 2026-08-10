import type { PoseCraftDocument, PoseCraftExportMetadata } from "./types";
import { getArchetypeSpec } from "./state";
import { buildSemanticPackage } from "./semanticLabels";

export function buildExportMetadata(
  document: PoseCraftDocument,
  renderer: "webgl" | "webgpu",
): PoseCraftExportMetadata {
  const scene = document.currentScene;
  return {
    schemaVersion: scene.schemaVersion,
    revision: scene.revision,
    exportedAt: new Date().toISOString(),
    sceneName: scene.name,
    figureCount: scene.figures.length,
    primitiveCount: scene.primitives.length,
    lensMm: scene.camera.lensMm,
    aspect: scene.camera.aspect,
    renderer,
  };
}

export function buildSceneExport(document: PoseCraftDocument, renderer: "webgl" | "webgpu") {
  const payload = {
    metadata: buildExportMetadata(document, renderer),
    scene: document.currentScene,
    savedVersions: document.savedVersions.map((version) => ({
      id: version.id,
      label: version.label,
      savedAt: version.savedAt,
      revision: version.revision,
    })),
  };
  return new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
}

/**
 * Final Mandatory GO (STORY): the staging reference / storyboard handoff
 * package. Preserves the full creator staging intent so Image Generation /
 * Storyboard can reconstruct the scene:
 *  - Per figure: modelId, archetype, color, transform, pose (archetype
 *    figures only), custom asset reference (custom figures only)
 *  - Furniture: kind + transform (incl. walls + window walls)
 *  - Camera: lens, aspect, orbit, target, guides
 */
export function buildReferenceExport(
  document: PoseCraftDocument,
  renderer: "webgl" | "webgpu",
  snapshotDataUrl: string,
) {
  const scene = document.currentScene;
  const semantic = buildSemanticPackage(document);
  const payload = {
    metadata: buildExportMetadata(document, renderer),
    snapshotDataUrl,
    notes: scene.notes,
    sceneName: scene.name,
    /** Co-Director / Image Gen / Storyboard semantic layer (labels ≠ ids). */
    semantic,
    figures: scene.figures.map((figure) => {
      const spec = getArchetypeSpec(figure.archetypeId);
      const isCustom = figure.kind === "custom";
      return {
        id: figure.id,
        label: figure.name,
        name: figure.name,
        role: figure.role ?? "unspecified",
        kind: isCustom ? "custom" : "archetype",
        type: isCustom ? "custom-figure" : figure.archetypeId,
        archetypeId: figure.archetypeId,
        modelId: isCustom ? "custom-mesh" : spec.modelId,
        colorId: figure.colorId,
        position: figure.position,
        rotationY: figure.rotationY,
        scale: figure.scale,
        pose: isCustom ? undefined : figure.pose,
        poseId: figure.poseId ?? null,
        poseLabel: figure.poseLabel ?? null,
        eyelineTargetId: figure.eyelineTargetId ?? null,
        customAssetId: isCustom ? figure.customAssetId : undefined,
        customAssetName: isCustom ? figure.customAssetName : undefined,
        characterId: figure.characterId ?? null,
        identityId: figure.identityId ?? null,
      };
    }),
    furniture: scene.primitives.map((primitive) => ({
      id: primitive.id,
      label: primitive.name,
      name: primitive.name,
      kind: primitive.kind,
      type: primitive.kind,
      position: primitive.position,
      rotationY: primitive.rotationY ?? 0,
      scale: primitive.scale ?? 1,
      size: primitive.size,
      color: primitive.color,
    })),
    objects: semantic.objects,
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
  return new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function downloadDataUrl(dataUrl: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = dataUrl;
  anchor.download = filename;
  anchor.click();
}
