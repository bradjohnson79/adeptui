export type ImagePipelineQualityProfile = "quick" | "enhanced" | "cinematic" | "studio-master";
export type ImagePipelineDeploymentPreference = "local" | "api" | "best-match";
export type ImagePipelineReadiness = "ready" | "warning" | "blocked";
export type ImagePipelineStageStatus = "pending" | "ready" | "blocked" | "skipped" | "complete";
export type ImagePipelineStagingRecommendation = "poseCraft" | "spatialMap" | "direct";
export type ImagePipelineApprovalStatus = "not-required" | "required" | "approved" | "blocked";

export type ProductionImageRequest = {
  projectId: string;
  prompt: string;
  purpose: string;
  qualityProfile: ImagePipelineQualityProfile;
  deploymentPreference: ImagePipelineDeploymentPreference;
  styleProfileId?: string | null;
  allowApiDeployment?: boolean;
  candidateCount?: number;
  projectContext?: Record<string, unknown>;
  characterIds?: string[];
  referenceAssetIds?: string[];
  spatialMapPayload?: Record<string, unknown> | null;
  poseControlPayload?: Record<string, unknown> | null;
  continuityNotes?: string[];
  creatorNotes?: string | null;
};

export type CreativeDirectionPacket = {
  scenePurpose: string;
  audienceFocus: string[];
  composition: string;
  lens: string;
  cameraHeight: string;
  mood: string;
  lighting: string;
  color: string;
  movementSuggestion: string;
  visualPriority: string;
  cameraStance: "observational" | "participatory";
  lightingEmotion: string;
  scenePurposeClass: string;
  symmetry: "symmetrical" | "asymmetrical" | "mixed";
  visualLanguageProfileId?: string | null;
  creatorSummary?: string | null;
};

export type ImagePipelineApprovalRequirement = {
  requirementId: string;
  kind: string;
  status: ImagePipelineApprovalStatus;
  reason?: string | null;
  creatorTip?: string | null;
  approvedBy?: string | null;
  approvedAt?: string | null;
};

export type ImagePipelineStage = {
  stageKey: string;
  label: string;
  description: string;
  enabled: boolean;
  required: boolean;
  status: ImagePipelineStageStatus;
  summary?: string | null;
};

export type ImagePipelineModelRoute = {
  routeId: string;
  workflowKey: string;
  modelFamily: string;
  providerKind: string;
  provider: string;
  deploymentTarget: "local" | "api";
  certified: boolean;
  requiresApproval: boolean;
  approvedForUse: boolean;
  approvalReason?: string | null;
  readiness: ImagePipelineReadiness;
  honestyNote?: string | null;
  provenance: Record<string, unknown>;
};

export type ImagePipelineReferenceAssignment = {
  assignmentId: string;
  assetId?: string | null;
  referenceId?: string | null;
  displayName: string;
  semanticRole: string;
  semanticRoles: string[];
  sourceType: string;
  characterId?: string | null;
  lockLevel: string;
  dominantColorHex?: string | null;
  notes?: string | null;
};

export type ImagePipelineControlPackage = {
  controlId: string;
  stagingRecommendation: ImagePipelineStagingRecommendation;
  projectPolicy: string;
  poseCraft?: Record<string, unknown> | null;
  spatialEnvironment?: Record<string, unknown> | null;
  continuity?: Record<string, unknown> | null;
  honestyNotes: string[];
};

export type ImageGenerationPlan = {
  planId: string;
  projectId: string;
  createdAt: string;
  updatedAt: string;
  request: ProductionImageRequest;
  shotIntent: Record<string, unknown>;
  creativeDirection: CreativeDirectionPacket;
  references: ImagePipelineReferenceAssignment[];
  continuity?: Record<string, unknown> | null;
  controlPackage: ImagePipelineControlPackage;
  modelRoute: ImagePipelineModelRoute;
  stages: ImagePipelineStage[];
  approvalRequirements: ImagePipelineApprovalRequirement[];
  readiness: ImagePipelineReadiness;
  readinessReasons: string[];
  previewSummary: string;
  stageReceipts: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
};

export type ImagePipelineCandidateEvaluation = {
  candidateId: string;
  overallStatus: "pass" | "warning" | "fail" | "not-evaluated";
  summary: string;
  recommendedNextStep?: string | null;
  findings: Array<Record<string, unknown>>;
  defects: Array<Record<string, unknown>>;
  honestyNotes: string[];
};

export type ImagePipelineCandidate = {
  candidateId: string;
  groupId: string;
  projectId: string;
  planId: string;
  label: string;
  status: string;
  jobId?: string | null;
  assetId?: string | null;
  parentCandidateId?: string | null;
  previewText: string;
  explanation: string;
  creatorSelected: boolean;
  evaluation?: ImagePipelineCandidateEvaluation | null;
};

export type ImagePipelineCandidateGroup = {
  groupId: string;
  projectId: string;
  planId: string;
  status: string;
  requestedCount: number;
  candidates: ImagePipelineCandidate[];
  recommendedCandidateId?: string | null;
  selectedCandidateId?: string | null;
  explanation?: string | null;
};
