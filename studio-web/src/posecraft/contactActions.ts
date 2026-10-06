import type { CameraState, PoseCraftObject, PoseCraftScene } from "./types";

function objectsOf(scene: PoseCraftScene): PoseCraftObject[] {
  return scene.objects ?? [];
}

export function sitFigureOnObject(scene: PoseCraftScene, figureId: string, objectId: string): PoseCraftScene {
  const figure = scene.figures.find((item) => item.id === figureId);
  const obj = objectsOf(scene).find((item) => item.id === objectId) ?? scene.primitives.find((item) => item.id === objectId);
  if (!figure || !obj) return scene;
  const seatY = ("size" in obj && obj.size?.y) ? obj.size.y * 0.55 : 0.42;
  return {
    ...scene,
    figures: scene.figures.map((item) =>
      item.id === figureId
        ? {
            ...item,
            position: { x: obj.position.x, y: seatY, z: obj.position.z },
            rotationY: "rotation" in obj && obj.rotation ? obj.rotation.y : item.rotationY,
            poseId: "rest-seated",
            poseLabel: "Sitting",
          }
        : item,
    ),
    revision: scene.revision + 1,
    updatedAt: new Date().toISOString(),
  };
}

export function lookFigureAt(scene: PoseCraftScene, figureId: string, targetId: string): PoseCraftScene {
  const figure = scene.figures.find((item) => item.id === figureId);
  const target =
    scene.figures.find((item) => item.id === targetId) ||
    objectsOf(scene).find((item) => item.id === targetId);
  if (!figure || !target) return scene;
  const dx = target.position.x - figure.position.x;
  const dz = target.position.z - figure.position.z;
  const yaw = (Math.atan2(dx, dz) * 180) / Math.PI;
  return {
    ...scene,
    figures: scene.figures.map((item) =>
      item.id === figureId ? { ...item, rotationY: yaw, eyelineTargetId: targetId } : item,
    ),
    revision: scene.revision + 1,
    updatedAt: new Date().toISOString(),
  };
}

export function focusCamera(scene: PoseCraftScene, kind: "stage" | "figure" | "torso" | "head" | "face" | "object", subjectId?: string | null): PoseCraftScene {
  const camera: CameraState = { ...scene.camera, minZ: 0.05, focusKind: kind, focusId: subjectId ?? null };
  if (kind === "stage") {
    camera.radius = 10;
    camera.target = { x: 0, y: 1.2, z: 0 };
  } else if (subjectId) {
    const figure = scene.figures.find((item) => item.id === subjectId);
    const obj = objectsOf(scene).find((item) => item.id === subjectId);
    const pos = figure?.position || obj?.position;
    if (pos) {
      const y = kind === "face" ? 1.68 : kind === "head" ? 1.62 : kind === "torso" ? 1.05 : 0.9;
      camera.target = { x: pos.x, y, z: pos.z };
      camera.radius = kind === "face" ? 0.42 : kind === "head" ? 0.55 : kind === "torso" ? 1.8 : 3.2;
    }
  }
  return { ...scene, camera, revision: scene.revision + 1, updatedAt: new Date().toISOString() };
}
