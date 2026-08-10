export type SpatialReferenceCharacter = {
  id: string;
  label: string;
  characterId: string;
  pose?: string;
  expression?: string;
  eyeLine?: string;
  assetId?: string | null;
};

export type SpatialReferenceProp = {
  id: string;
  label: string;
  propId?: string | null;
  category?: string;
  state?: string;
  assetId?: string | null;
};

export type SpatialReferenceCamera = {
  id: string;
  label: string;
  lensMm?: number;
  shotType?: string;
  hero?: boolean;
};

export type SpatialMapDocumentReference = {
  id: string;
  title: string;
  updatedAt?: string;
  sceneId?: string | null;
  backgroundAssetId?: string | null;
  masterEnvironmentPrompt?: string;
  cameras: SpatialReferenceCamera[];
  characters: SpatialReferenceCharacter[];
  props: SpatialReferenceProp[];
};

export type SpatialReferenceSelection = {
  spatialMapId?: string;
  spatialMapVersion?: string;
  spatialCameraId?: string;
  spatialStartCameraId?: string;
  spatialEndCameraId?: string;
};

export type SpatialReferenceSummary = {
  camera: string;
  characters: string;
  props: string;
  background: string;
};

export function summarizeSpatialMap(document: SpatialMapDocumentReference | null | undefined): SpatialReferenceSummary {
  if (!document) {
    return {
      camera: "No spatial map selected yet.",
      characters: "No characters staged.",
      props: "No props staged.",
      background: "No background reference attached yet.",
    };
  }

  const heroCamera = document.cameras.find((camera) => camera.hero) || document.cameras[0];
  const camera = heroCamera
    ? `${heroCamera.label}${heroCamera.shotType ? ` · ${heroCamera.shotType.replace(/_/g, " ")}` : ""}${heroCamera.lensMm ? ` · ${Math.round(heroCamera.lensMm)}mm` : ""}`
    : "No camera saved yet.";

  const characters = document.characters.length
    ? document.characters
        .slice(0, 3)
        .map((item) => item.label || item.characterId || "Character")
        .join(", ")
    : "No characters staged.";

  const props = document.props.length
    ? document.props
        .slice(0, 3)
        .map((item) => item.label || item.propId || "Prop")
        .join(", ")
    : "No props staged.";

  const background = document.masterEnvironmentPrompt?.trim()
    || (document.backgroundAssetId ? "Background plate linked." : "")
    || "No background reference attached yet.";

  return { camera, characters, props, background };
}
