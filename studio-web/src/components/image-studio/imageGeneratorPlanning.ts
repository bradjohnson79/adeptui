/**
 * Co-Director awareness + local persist for Cinematic Image Generator.
 * Module-store pattern mirrors Environment Creator (no optional session hooks).
 */
import type { CisAuthorityRef } from "./cisAuthorityTypes";
import { parseIgPromptTokens } from "./igPromptTokens";

export type ImageGeneratorPlanningState = {
  prompt: string;
  negativePrompt?: string;
  authorityRefs: CisAuthorityRef[];
  referenceAssetIds: string[];
  unresolvedTags: string[];
  provenance?: string;
  updatedAt: string;
  /** Optional generation controls published from Cinematic Image Studio. */
  generationMode?: string;
  category?: string;
  batchSize?: number;
  modelId?: string;
  generatorId?: string;
  aspectRatio?: string;
  resolution?: string;
};

export type ImageGeneratorReferenceRow = {
  kind: CisAuthorityRef["kind"];
  role: string;
  assetId: string;
  name: string;
  label: string;
  token: string;
};

export type ImageGeneratorPoseCraftSnapshot = {
  attached: boolean;
  imageAssetId?: string;
  name?: string;
  chip?: string;
};

export type ImageGeneratorSerializedPlan = {
  prompt: string;
  negativePrompt?: string;
  authorityRefs: CisAuthorityRef[];
  referenceAssetIds: string[];
  promptTags: string[];
  unresolvedTags: string[];
  provenance?: string;
  updatedAt: string;
  selectedCharacters: CisAuthorityRef[];
  selectedProps: CisAuthorityRef[];
  selectedEnvironment: CisAuthorityRef | null;
  selectedPoseCraft: CisAuthorityRef | null;
  selectedGeneric: CisAuthorityRef[];
  references: ImageGeneratorReferenceRow[];
  poseCraft: ImageGeneratorPoseCraftSnapshot;
  generationMode?: string;
  category?: string;
  batchSize?: number;
  modelId?: string;
  generatorId?: string;
  aspectRatio?: string;
  resolution?: string;
};

const DRAFT_KEY_PREFIX = "adept_image_generator_plan_";

export function imageGeneratorDraftKey(projectId: string): string {
  return `${DRAFT_KEY_PREFIX}${projectId}`;
}

export function emptyImageGeneratorPlanning(): ImageGeneratorPlanningState {
  return {
    prompt: "",
    negativePrompt: "",
    authorityRefs: [],
    referenceAssetIds: [],
    unresolvedTags: [],
    provenance: "cinematic_image_studio",
    updatedAt: new Date().toISOString(),
  };
}

function refToReferenceRow(ref: CisAuthorityRef): ImageGeneratorReferenceRow {
  const name = ref.name || "";
  const token = ref.chip || "";
  return {
    kind: ref.kind,
    role: ref.kind,
    assetId: ref.assetId || "",
    name,
    label: name || token || ref.assetId || "?",
    token,
  };
}

function poseCraftFromRefs(refs: CisAuthorityRef[]): ImageGeneratorPoseCraftSnapshot {
  const pose = refs.find((r) => r.kind === "posecraft") || null;
  if (!pose) return { attached: false };
  return {
    attached: true,
    imageAssetId: pose.assetId || undefined,
    name: pose.name || undefined,
    chip: pose.chip || undefined,
  };
}

export function serializeImageGeneratorPlan(
  state: ImageGeneratorPlanningState,
): ImageGeneratorSerializedPlan {
  const refs = Array.isArray(state.authorityRefs) ? state.authorityRefs : [];
  const selectedCharacters = refs.filter((r) => r.kind === "character");
  const selectedProps = refs.filter((r) => r.kind === "prop");
  const selectedEnvironment = refs.find((r) => r.kind === "environment") || null;
  const selectedPoseCraft = refs.find((r) => r.kind === "posecraft") || null;
  const selectedGeneric = refs.filter((r) => r.kind === "other");
  return {
    prompt: state.prompt,
    negativePrompt: state.negativePrompt,
    authorityRefs: refs,
    referenceAssetIds: state.referenceAssetIds,
    promptTags: parseIgPromptTokens(state.prompt).map((t) => t.raw),
    unresolvedTags: state.unresolvedTags,
    provenance: state.provenance || "cinematic_image_studio",
    updatedAt: state.updatedAt || new Date().toISOString(),
    selectedCharacters,
    selectedProps,
    selectedEnvironment,
    selectedPoseCraft,
    selectedGeneric,
    references: refs.map(refToReferenceRow),
    poseCraft: poseCraftFromRefs(refs),
    generationMode: state.generationMode,
    category: state.category,
    batchSize: state.batchSize,
    modelId: state.modelId,
    generatorId: state.generatorId,
    aspectRatio: state.aspectRatio,
    resolution: state.resolution,
  };
}

export function loadImageGeneratorDraft(projectId: string): Partial<ImageGeneratorPlanningState> | null {
  if (!projectId || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(imageGeneratorDraftKey(projectId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ImageGeneratorPlanningState>;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function saveImageGeneratorDraft(projectId: string, state: ImageGeneratorPlanningState): void {
  if (!projectId || typeof window === "undefined") return;
  try {
    window.localStorage.setItem(imageGeneratorDraftKey(projectId), JSON.stringify(state));
  } catch {
    /* storage unavailable */
  }
}

export function clearImageGeneratorDraft(projectId: string): void {
  if (!projectId || typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(imageGeneratorDraftKey(projectId));
  } catch {
    /* ignore */
  }
}

type PlanningListener = (snapshot: ImageGeneratorSerializedPlan | null) => void;
const planningByProject = new Map<string, ImageGeneratorSerializedPlan>();
const listeners = new Set<PlanningListener>();

export function publishImageGeneratorPlanning(
  projectId: string,
  state: ImageGeneratorPlanningState | null,
): void {
  if (!projectId) return;
  if (!state) {
    planningByProject.delete(projectId);
    listeners.forEach((fn) => fn(null));
    return;
  }
  const snap = serializeImageGeneratorPlan(state);
  planningByProject.set(projectId, snap);
  listeners.forEach((fn) => fn(snap));
}

export function getImageGeneratorPlanningSnapshot(
  projectId: string,
): ImageGeneratorSerializedPlan | null {
  if (!projectId) return null;
  return planningByProject.get(projectId) || null;
}

export function subscribeImageGeneratorPlanning(listener: PlanningListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
