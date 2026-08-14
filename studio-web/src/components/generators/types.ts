/**
 * Shared generator source types — Character Creator, Prop Creator, and any
 * other product that reuses GeneratorSourceSelector.
 */
export type GeneratorSourceKind = "local" | "api";

export type GeneratorOption = {
  id: string;
  label: string;
  family?: string;
  providerKind?: "local" | "cloud";
  /** Readiness / Certified state */
  executable: boolean;
  status?: string;
  /** Numeric credit balance only when the provider actually exposes one. */
  credits?: number | null;
  /** Human availability when no numeric balance: "Connected" | "Balance unavailable" */
  availability?: string;
  /** Family can consume reference pixels (any Certified reference-capable key). */
  supportsReferences?: boolean;
  /** Family has a real img2img/edit workflow for Stage 2 style refinement. */
  supportsEditing?: boolean;
};

export type GeneratorSourceState = {
  enabled: boolean;
  selectedId: string;
  /** Optional Stage 2 style-refinement engine. */
  stage2Enabled?: boolean;
  stage2SelectedId?: string;
};

export type GeneratorSources = {
  local: GeneratorSourceState;
  api: GeneratorSourceState;
};

export const DEFAULT_GENERATOR_SOURCES: GeneratorSources = {
  local: { enabled: true, selectedId: "" },
  api: { enabled: false, selectedId: "" },
};

export type CharacterGenerationMode = "REFERENCE_CONDITIONED" | "PROFILE_GUIDED" | "UNSUPPORTED";

/**
 * Authoritative Character Sheet mode. A Character Reference does not disable
 * txt2img families — they run PROFILE_GUIDED without reference pixels.
 * Only UNSUPPORTED blocks Generate.
 */
export function resolveCharacterGenerationMode(
  option: GeneratorOption | null | undefined,
  hasReference: boolean,
): CharacterGenerationMode {
  if (!option || option.executable === false) return "UNSUPPORTED";
  if (hasReference && option.supportsReferences) return "REFERENCE_CONDITIONED";
  return "PROFILE_GUIDED";
}

export function generationModeWireValue(mode: CharacterGenerationMode): "profile_guided" | "reference_conditioned" | null {
  if (mode === "PROFILE_GUIDED") return "profile_guided";
  if (mode === "REFERENCE_CONDITIONED") return "reference_conditioned";
  return null;
}

/** True incompatibility only: missing/non-executable runtime. */
export function isIdentityEligible(option: GeneratorOption): boolean {
  return resolveCharacterGenerationMode(option, false) !== "UNSUPPORTED";
}

export function identityDisabledReason(option: GeneratorOption): string | null {
  return option.executable === false
    ? `${option.label} is not available (runtime, model, or provider missing).`
    : null;
}

/**
 * Mode label for a local/cloud option. A reference does NOT disable
 * text-to-image families — they run the text mode (Profile Guided /
 * Description Guided) without reference pixels.
 */
export function conditioningModeLabel(
  option: GeneratorOption,
  hasReference: boolean,
  textModeLabel: string,
): string | null {
  if (!hasReference) return null;
  return option.supportsReferences ? "Reference Conditioned" : textModeLabel;
}
