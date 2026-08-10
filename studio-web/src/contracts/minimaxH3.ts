export type H3SourceSurface =
  | "codirector"
  | "text-to-video"
  | "one-frame"
  | "three-frame"
  | "timeline"
  | "timeline-retake"
  | "library"
  | "audio-studio"
  | "api"
  | "other";

export type H3Mode =
  | "text-to-video"
  | "one-frame"
  | "first-last"
  | "three-frame"
  | "reference"
  | "edit";

export type AdeptMiniMaxH3Request = {
  projectId: string;
  prompt: string;
  sourceSurface: H3SourceSurface;
  mode: H3Mode;
  deployment?: "local_weights" | "api" | "local";
  territory?: string;
  durationSec?: number;
  approvalId?: string | null;
  referenceAssignments?: Array<{
    role: string;
    assetId: string;
    displayName?: string;
    sourceType?: string;
    notes?: string | null;
  }>;
  timelineContext?: {
    sceneId?: string | null;
    shotId?: string | null;
    assemblyPlan?: string | null;
    notes?: string[];
  } | null;
  creatorNotes?: string | null;
  retake?: boolean;
  sourceTakeId?: string | null;
  deltaInstruction?: string | null;
  originalPrompt?: string | null;
};

export type H3FallbackOffer = {
  providerId: string;
  label: string;
  reason: string;
  requiresExplicitApproval: boolean;
  preservesInputs: string[];
  confirmationPrompt?: string;
};

export type H3PreflightResult = {
  status: "ready" | "blocked" | "needs_approval";
  territory: string;
  deployment: string;
  durationSec: number;
  blockers: string[];
  warnings: string[];
  approvalRequired: boolean;
  fallbackOffer?: H3FallbackOffer | null;
};

export type H3ThreeFrameInterval = {
  intervalId: string;
  label: string;
  startRole: string;
  endRole: string;
  startAssetId: string;
  endAssetId: string;
  creatorGoal: string;
};

export type H3Plan = {
  planId: string;
  projectId: string;
  mode: H3Mode;
  sourceSurface: H3SourceSurface;
  creatorSummary: string;
  creatorDisclosure: string;
  deployment: string;
  status: string;
  preflight?: H3PreflightResult | null;
  fallbackOffer?: H3FallbackOffer | null;
  threeFramePlan?: {
    strategy: string;
    nativeSupported: boolean;
    disclosureText: string;
    intervals: H3ThreeFrameInterval[];
    assemblyNotes: string[];
  } | null;
};
