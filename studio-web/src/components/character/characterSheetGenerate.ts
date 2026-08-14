/**
 * Character Sheet Generate request builder — testable without mounting React.
 * Mode resolution lives in generators/types (shared with the selector).
 */
import {
  generationModeWireValue,
  resolveCharacterGenerationMode,
  type GeneratorOption,
  type GeneratorSourceState,
} from "../generators/types";

export const CHARACTER_SHEET_START_ERROR_PREFIX = "Character Sheet generation could not start:";

/** Amendment F5 — normal Character Creator / Express product UX. */
export const CHARACTER_SHEET_PRODUCT_CANDIDATE_COUNT = 4;

/** Minimal live proof only. Do not use as the product default. */
export const CHARACTER_SHEET_E2E_CANDIDATE_COUNT = 1;

type Sources = { local: GeneratorSourceState; api: GeneratorSourceState };

export function characterGenerateBlockReason(input: {
  name?: string | null;
  sources: Sources;
  generating?: boolean;
  disabled?: boolean;
  selectedLocal?: GeneratorOption | null;
  selectedApi?: GeneratorOption | null;
}): string | null {
  if (input.disabled) return `${CHARACTER_SHEET_START_ERROR_PREFIX} Character Sheet generation is unavailable.`;
  if (input.generating) return null;
  if (!input.name?.trim()) return `${CHARACTER_SHEET_START_ERROR_PREFIX} Character Profile is missing required name.`;
  if (!input.sources.local.enabled && !input.sources.api.enabled) {
    return `${CHARACTER_SHEET_START_ERROR_PREFIX} Enable a Local or Cloud generator to create character sheets.`;
  }
  if (input.sources.local.enabled && input.sources.local.selectedId) {
    const mode = resolveCharacterGenerationMode(input.selectedLocal, false);
    if (input.selectedLocal && mode === "UNSUPPORTED") {
      return `${CHARACTER_SHEET_START_ERROR_PREFIX} Selected model is not ready.`;
    }
  }
  if (input.sources.api.enabled && input.sources.api.selectedId) {
    const mode = resolveCharacterGenerationMode(input.selectedApi, false);
    if (input.selectedApi && mode === "UNSUPPORTED") {
      return `${CHARACTER_SHEET_START_ERROR_PREFIX} Selected model is not ready.`;
    }
  }
  return null;
}

export function buildCharacterSheetStartBody(input: {
  profileVisualStyle?: string | null;
  sources: Sources;
  hasReference: boolean;
  localOptions?: GeneratorOption[];
  apiOptions?: GeneratorOption[];
  /** Override only for E2E/minimal live proof. Product default is 4. */
  candidateCount?: number;
}): {
  candidateCount: number;
  visualStyle?: string;
  includeDetails: boolean;
  includePerformance: boolean;
  generationMode?: "profile_guided" | "reference_conditioned";
  generatorSources: {
    local: {
      family?: string;
      stage2Family?: string;
      stage2Enabled: boolean;
    } | null;
    api: { model?: string } | null;
  };
} {
  const localOpt =
    input.localOptions?.find((o) => o.id === input.sources.local.selectedId) ||
    (input.sources.local.selectedId
      ? ({
          id: input.sources.local.selectedId,
          label: input.sources.local.selectedId,
          executable: true,
          supportsReferences: input.sources.local.selectedId === "zimage",
        } satisfies GeneratorOption)
      : null);
  const mode = input.sources.local.enabled
    ? resolveCharacterGenerationMode(localOpt, input.hasReference)
    : input.sources.api.enabled
      ? resolveCharacterGenerationMode(
          input.apiOptions?.find((o) => o.id === input.sources.api.selectedId) || {
            id: input.sources.api.selectedId,
            label: input.sources.api.selectedId,
            executable: true,
          },
          input.hasReference,
        )
      : "UNSUPPORTED";
  const wire = generationModeWireValue(mode);
  const candidateCount = Math.max(
    1,
    Math.min(6, input.candidateCount ?? CHARACTER_SHEET_PRODUCT_CANDIDATE_COUNT),
  );
  return {
    candidateCount,
    visualStyle: input.profileVisualStyle || undefined,
    includeDetails: false,
    includePerformance: false,
    generationMode: wire || undefined,
    generatorSources: {
      local: input.sources.local.enabled
        ? {
            family: input.sources.local.selectedId || undefined,
            stage2Family: input.sources.local.stage2Enabled
              ? input.sources.local.stage2SelectedId || undefined
              : undefined,
            stage2Enabled: input.sources.local.stage2Enabled || false,
          }
        : null,
      api: input.sources.api.enabled ? { model: input.sources.api.selectedId || undefined } : null,
    },
  };
}

export function formatCharacterSheetStartError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error || "Generation request was rejected.");
  if (raw.startsWith(CHARACTER_SHEET_START_ERROR_PREFIX)) return raw;
  return `${CHARACTER_SHEET_START_ERROR_PREFIX} ${raw || "Generation request was rejected."}`;
}
