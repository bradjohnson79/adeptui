export type ERSStatus =
  | "draft"
  | "spatial_pending"
  | "views_pending"
  | "continuity_review"
  | "composition_ready"
  | "registered"
  | "approved"
  | "blocked";

export type ERSReadiness = "ready" | "warning" | "blocked";
export type ERSViewDirection = "north" | "east" | "south" | "west";
export type ERSViewStatus = "missing" | "planned" | "queued" | "ready" | "approved" | "blocked";
export type ERSThreeDTruthLabel = "illustrative" | "isometric" | "derived" | "true";
export type ERSExportKind = "png" | "pdf" | "offline_html";

export type EnvironmentProfile = {
  environmentName: string;
  description: string;
  environmentType: string;
  storyPurpose: string;
  visualDNA: string[];
  atmosphere: string[];
  timeOfDay: string;
  weather: string;
  scale: string;
  architecture: string;
  materials: string[];
  colorPalette: string[];
  lightingNotes: string[];
  continuityLocks: string[];
  creatorNotes?: string | null;
};

export type SpatialMapReference = {
  mapId: string;
  mapVersion?: string | null;
  sceneId?: string | null;
  locationId?: string | null;
  northLockDirection: ERSViewDirection;
  referenceBundleSummary: string;
  warnings: string[];
  directionalPrompts: Record<string, string>;
};

export type DirectionalViewRecord = {
  direction: ERSViewDirection;
  title: string;
  prompt: string;
  sourceDirection: string;
  imagePipelinePlanId?: string | null;
  candidateGroupId?: string | null;
  selectedCandidateId?: string | null;
  approvedAssetId?: string | null;
  status: ERSViewStatus;
  continuityNotes: string[];
  warnings: string[];
};

export type ContinuityFinding = {
  findingId: string;
  severity: "info" | "warning" | "error";
  code: string;
  title: string;
  message: string;
  affectedDirections: ERSViewDirection[];
  recommendedAction?: string | null;
};

export type ContinuityValidationReport = {
  status: ERSReadiness;
  summary: string;
  findings: ContinuityFinding[];
  repairStrategy: string;
  preservedDirections: ERSViewDirection[];
  evaluatedAt: string;
  note?: string | null;
};

export type ERSCompositionRecord = {
  sheetTitle: string;
  subtitle: string;
  heroSummary: string;
  profileHighlights: string[];
  continuitySummary: string;
  renderedAssetIds: Record<string, string>;
  renderedFiles: Record<string, string>;
  lastRenderedAt?: string | null;
};

export type ERSProjectRegistration = {
  locationStableId?: string | null;
  locationDisplayName?: string | null;
  libraryFolderPath?: string | null;
  linkedSceneIds: string[];
  projectMemoryNotes: string[];
  registeredAt?: string | null;
};

export type ERSExportRecord = {
  exportKind: ERSExportKind;
  status: "not_created" | "created" | "failed";
  assetId?: string | null;
  filePath?: string | null;
  archiveName?: string | null;
  message: string;
  createdAt?: string | null;
};

export type ERSProvenanceRecord = {
  createdAt: string;
  actor: string;
  source: string;
  note?: string | null;
  details: Record<string, unknown>;
};

export type EnvironmentReferenceSheet = {
  schemaVersion: number;
  sheetId: string;
  projectId: string;
  sceneId?: string | null;
  name: string;
  description: string;
  status: ERSStatus;
  createdAt: string;
  updatedAt: string;
  profile: EnvironmentProfile;
  spatialMap?: SpatialMapReference | null;
  directionalViews: DirectionalViewRecord[];
  optionalThreeD?: {
    truthLabel: ERSThreeDTruthLabel;
    status: "not_requested" | "linked" | "blocked";
    assetId?: string | null;
    note: string;
  } | null;
  continuity: ContinuityValidationReport;
  composition: ERSCompositionRecord;
  ers_composite_asset_id?: string | null;
  registration: ERSProjectRegistration;
  exports: ERSExportRecord[];
  provenance?: ERSProvenanceRecord | null;
};

export type EnvironmentReferenceSheetSummary = {
  sheetId: string;
  projectId: string;
  name: string;
  status: ERSStatus;
  sceneId?: string | null;
  locationStableId?: string | null;
  continuityStatus: ERSReadiness;
  approvedDirections: ERSViewDirection[];
  ers_composite_asset_id?: string | null;
  has_reference?: boolean;
  exportKinds: ERSExportKind[];
  updatedAt: string;
};
