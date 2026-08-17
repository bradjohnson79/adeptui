/**
 * Character Sheet Generate request builder — testable without mounting React.
 * Mode resolution lives in generators/types (shared with the selector).
 */
import type { GeneratorOption } from "../generators/types";
import {
  buildGeneratorSourcesPayload,
  firstPlannedGenerationMode,
  hasExecutableSource,
  localInventoryHasExecutableSource,
  summarizeGenerationPlan,
  type CharacterGeneratorPlan,
  type CharacterSheetGeneratorSourcesPayload,
} from "./characterGeneratorPlan";

export const CHARACTER_SHEET_START_ERROR_PREFIX = "Character Sheet generation could not start:";

/** Creator-facing reason when the plan has no executable source (CDX-009). */
export function noExecutableSourceReason(
  plan: CharacterGeneratorPlan,
  localOptions?: GeneratorOption[],
): string {
  const cloudOff = !(plan.apiEnabled && plan.apiModels.some((row) => row.enabled));
  if (cloudOff && plan.localEnabled && !localInventoryHasExecutableSource(localOptions)) {
    return `${CHARACTER_SHEET_START_ERROR_PREFIX} No local generator is currently available and Cloud is off. Enable a Cloud generator or start the local runtime to create character sheets.`;
  }
  return `${CHARACTER_SHEET_START_ERROR_PREFIX} Enable a Local or Cloud generator to create character sheets.`;
}

/** @deprecated Use per-generator batchCount default 1. Kept for E2E override docs. */
export const CHARACTER_SHEET_PRODUCT_CANDIDATE_COUNT = 1;

/** Minimal live proof only. Do not use as the product default. */
export const CHARACTER_SHEET_E2E_CANDIDATE_COUNT = 1;

export function characterGenerateBlockReason(input: {
  name?: string | null;
  plan: CharacterGeneratorPlan;
  generating?: boolean;
  disabled?: boolean;
  localOptions?: GeneratorOption[];
}): string | null {
  if (input.disabled) return `${CHARACTER_SHEET_START_ERROR_PREFIX} Character Sheet generation is unavailable.`;
  if (input.generating) return null;
  if (!input.name?.trim()) return `${CHARACTER_SHEET_START_ERROR_PREFIX} Character Profile is missing required name.`;
  if (!input.plan.localEnabled && !input.plan.apiEnabled) {
    return `${CHARACTER_SHEET_START_ERROR_PREFIX} Enable a Local or Cloud generator to create character sheets.`;
  }
  const summary = summarizeGenerationPlan(input.plan, input.localOptions);
  if (summary.totalSheets < 1 || !hasExecutableSource(input.plan, input.localOptions)) {
    return noExecutableSourceReason(input.plan, input.localOptions);
  }
  return null;
}

export function buildCharacterSheetStartBody(input: {
  profileVisualStyle?: string | null;
  plan: CharacterGeneratorPlan;
  hasReference: boolean;
  localOptions?: GeneratorOption[];
  apiOptions?: GeneratorOption[];
}): {
  visualStyle?: string;
  includeDetails: boolean;
  includePerformance: boolean;
  generationMode?: "profile_guided" | "reference_conditioned";
  generatorSources: CharacterSheetGeneratorSourcesPayload;
  candidateCount: number;
} {
  const summary = summarizeGenerationPlan(input.plan, input.localOptions);
  const generationMode = firstPlannedGenerationMode(
    input.plan,
    input.hasReference,
    input.localOptions || [],
    input.apiOptions || [],
  );
  return {
    visualStyle: input.profileVisualStyle || undefined,
    includeDetails: false,
    includePerformance: false,
    generationMode,
    generatorSources: buildGeneratorSourcesPayload(input.plan),
    candidateCount: summary.totalSheets,
  };
}

export function formatCharacterSheetStartError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error || "Generation request was rejected.");
  if (raw.startsWith(CHARACTER_SHEET_START_ERROR_PREFIX)) return raw;
  return `${CHARACTER_SHEET_START_ERROR_PREFIX} ${raw || "Generation request was rejected."}`;
}
