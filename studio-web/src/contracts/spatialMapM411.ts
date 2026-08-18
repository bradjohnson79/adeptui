export type SpatialMapStudioTab = "map" | "collage360" | "cameras" | "export";

export type ProviderHonestyMode = "approximate_translation" | "native_coordinates";
export type SpatialPathSubjectType = "character" | "prop" | "camera";
export type SpatialBundleTarget = "image" | "video";
export type SpatialCaptureMode = "environment_only" | "include_characters";
export type Spatial360ViewStatus = "planned" | "captured" | "approved";

export type SpatialDirection =
  | "front"
  | "front_right"
  | "right"
  | "rear_right"
  | "rear"
  | "rear_left"
  | "left"
  | "front_left"
  | "ceiling"
  | "floor"
  | "hero";

export type SpatialRequiredDirection =
  | "front"
  | "front_right"
  | "right"
  | "rear_right"
  | "rear"
  | "rear_left"
  | "left"
  | "front_left";

export type SpatialBounds = {
  coordinateSystem: "adept-world-v1";
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  minZ: number;
  maxZ: number;
};

export type SpatialAnchor = {
  id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  notes: string;
};

export type SpatialPlacement = {
  id: string;
  label: string;
  assetId?: string | null;
  anchorId?: string | null;
  notes: string;
  x: number;
  y: number;
  z: number;
  yawDegrees: number;
  pitchDegrees: number;
  rollDegrees: number;
  scale: number;
};

export type SpatialCharacterPlacement = SpatialPlacement & {
  characterId: string;
  pose: string;
  expression: string;
  eyeLine: string;
  providerHonesty: ProviderHonestyMode;
};

export type SpatialPropPlacement = SpatialPlacement & {
  propId?: string | null;
  category: string;
  state: string;
  providerHonesty: ProviderHonestyMode;
};

export type SpatialCamera = {
  id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  yawDegrees: number;
  pitchDegrees: number;
  rollDegrees: number;
  lensMm: number;
  heightMeters: number;
  shotType: string;
  targetCharacterIds: string[];
  hero: boolean;
  lockedFor360: boolean;
};

export type SpatialMovementWaypoint = {
  x: number;
  y: number;
  z: number;
  holdSeconds: number;
};

export type SpatialMovementPath = {
  id: string;
  label: string;
  subjectType: SpatialPathSubjectType;
  subjectId: string;
  waypoints: SpatialMovementWaypoint[];
  notes: string;
  loop: boolean;
};

export type Spatial360View = {
  direction: SpatialDirection;
  yawDegrees: number;
  assetId?: string | null;
  prompt: string;
  status: Spatial360ViewStatus;
  continuityScore: number;
  adjacencyWarnings: string[];
};

export type Spatial360Collage = {
  id: string;
  masterEnvironmentPrompt: string;
  captureMode: SpatialCaptureMode;
  cameraHeightMeters: number;
  lensMm: number;
  heroDirection?: SpatialDirection | null;
  views: Spatial360View[];
  continuityWarnings: string[];
  minimumDirectionsMet: boolean;
};

export type SpatialMapDocument = {
  schemaVersion: number;
  id: string;
  version: string;
  projectId: string;
  sceneId?: string | null;
  locationId?: string | null;
  title: string;
  notes: string;
  tags: string[];
  bounds: SpatialBounds;
  backgroundAssetId?: string | null;
  masterEnvironmentPrompt: string;
  providerHonesty: ProviderHonestyMode;
  anchors: SpatialAnchor[];
  characters: SpatialCharacterPlacement[];
  props: SpatialPropPlacement[];
  cameras: SpatialCamera[];
  paths: SpatialMovementPath[];
  collage?: Spatial360Collage | null;
  warnings: string[];
  variantOfId?: string | null;
  variantIds: string[];
  assignedSceneIds: string[];
  createdAt: string;
  updatedAt: string;
  savedAt?: string | null;
  savedVersion?: string | null;
};

export type SpatialMapCreateBody = {
  title?: string;
  sceneId?: string | null;
  locationId?: string | null;
  notes?: string;
  bounds?: SpatialBounds;
  backgroundAssetId?: string | null;
  masterEnvironmentPrompt?: string;
  providerHonesty?: ProviderHonestyMode;
};

export type SpatialMapUpdateBody = {
  title?: string;
  sceneId?: string | null;
  locationId?: string | null;
  notes?: string;
  tags?: string[];
  bounds?: SpatialBounds;
  backgroundAssetId?: string | null;
  masterEnvironmentPrompt?: string;
  providerHonesty?: ProviderHonestyMode;
};

export type SpatialCharacterPlacementBody = {
  characterId: string;
  label: string;
  assetId?: string | null;
  anchorId?: string | null;
  notes?: string;
  x?: number;
  y?: number;
  z?: number;
  yawDegrees?: number;
  pitchDegrees?: number;
  rollDegrees?: number;
  scale?: number;
  pose?: string;
  expression?: string;
  eyeLine?: string;
};

export type SpatialCharacterPlacementUpdateBody = Partial<
  Omit<SpatialCharacterPlacementBody, "characterId">
>;

export type SpatialPropPlacementBody = {
  label: string;
  propId?: string | null;
  assetId?: string | null;
  anchorId?: string | null;
  notes?: string;
  category?: string;
  state?: string;
  x?: number;
  y?: number;
  z?: number;
  yawDegrees?: number;
  pitchDegrees?: number;
  rollDegrees?: number;
  scale?: number;
};

export type SpatialPropPlacementUpdateBody = Partial<SpatialPropPlacementBody>;

export type SpatialCameraCreateBody = {
  label?: string;
  x?: number;
  y?: number;
  z?: number;
  yawDegrees?: number;
  pitchDegrees?: number;
  rollDegrees?: number;
  lensMm?: number;
  heightMeters?: number;
  shotType?: string;
  targetCharacterIds?: string[];
  hero?: boolean;
  lockedFor360?: boolean;
};

export type SpatialCameraUpdateBody = Partial<SpatialCameraCreateBody>;

export type SpatialMovementPathCreateBody = {
  label?: string;
  subjectType: SpatialPathSubjectType;
  subjectId: string;
  waypoints?: SpatialMovementWaypoint[];
  notes?: string;
  loop?: boolean;
};

export type SpatialAssignSceneBody = {
  sceneId: string;
  locationId?: string | null;
};

export type SpatialVariantCreateBody = {
  name: string;
  sceneId?: string | null;
  locationId?: string | null;
  notesSuffix?: string;
};

export type SpatialCollageCreateBody = {
  masterEnvironmentPrompt?: string;
  captureMode?: SpatialCaptureMode;
  cameraHeightMeters?: number;
  lensMm?: number;
  heroDirection?: SpatialDirection | null;
};

export type Spatial360ViewUpsertBody = {
  assetId?: string | null;
  prompt?: string;
  status?: Spatial360ViewStatus;
};

export type SpatialCapturePlanBody = {
  includeCharacters?: boolean;
  masterEnvironmentPrompt?: string;
  cameraHeightMeters?: number;
  lensMm?: number;
};

export type SpatialReferenceAsset = {
  assetId: string;
  kind: string;
  filename: string;
  path: string;
};

export type SpatialReferenceBundle = {
  documentId: string;
  documentVersion?: string | null;
  projectId: string;
  sceneId?: string | null;
  locationId?: string | null;
  target: SpatialBundleTarget;
  coordinateSystem: "adept-world-v1";
  providerHonesty: ProviderHonestyMode;
  environmentPrompt: string;
  backgroundAssetId?: string | null;
  referenceAssetIds: string[];
  assetReferences: SpatialReferenceAsset[];
  characters: SpatialCharacterPlacement[];
  props: SpatialPropPlacement[];
  primaryCamera?: SpatialCamera | null;
  movementPaths: SpatialMovementPath[];
  availableCollageDirections: SpatialDirection[];
  creatorPositionLabels: Record<string, string>;
  directionalPrompts: Record<string, string>;
  warnings: string[];
};

export type SpatialCaptureShot = {
  direction: SpatialDirection;
  yawDegrees: number;
  prompt: string;
};

export type SpatialCapturePlan = {
  documentId: string;
  captureMode: SpatialCaptureMode;
  masterEnvironmentPrompt: string;
  cameraHeightMeters: number;
  lensMm: number;
  coordinateSystem: "adept-world-v1";
  providerHonesty: ProviderHonestyMode;
  shots: SpatialCaptureShot[];
  instructions: string[];
};

export type SpatialMapListResponse = { documents: SpatialMapDocument[] };
export type SpatialMapDocumentResponse = { document: SpatialMapDocument };
export type SpatialReferenceBundleResponse = { bundle: SpatialReferenceBundle };
export type SpatialCapturePlanResponse = { plan: SpatialCapturePlan };
export type SpatialConsistencyCheckResponse = { warnings: string[] };

export const SPATIAL_MAP_LIMITS = {
  characters: 4,
  props: 4,
  cameras: 8,
} as const;

export const SPATIAL_REQUIRED_DIRECTIONS: SpatialRequiredDirection[] = [
  "front",
  "front_right",
  "right",
  "rear_right",
  "rear",
  "rear_left",
  "left",
  "front_left",
];

export function spatialMapCounts(document: SpatialMapDocument) {
  return {
    characters: document.characters.length,
    props: document.props.length,
    cameras: document.cameras.length,
  };
}

export function directionLabel(direction: SpatialDirection) {
  return direction
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
