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
  /** Setup registry provider id (API models). Never identify an API model by display name alone. */
  providerId?: string;
  /** Provider model id (API models). */
  modelId?: string;
  /** Readiness / Certified state */
  executable: boolean;
  status?: string;
  /** Numeric credit balance only when the provider actually exposes one. */
  credits?: number | null;
  /** Human availability when no numeric balance: "Connected" | "Balance unavailable" */
  availability?: string;
  capabilities?: string[];
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

/** Raw row from GET /api/imagegen-models (Local Generator roster). */
export type LocalGeneratorRow = {
  id: string;
  label: string;
  group?: string;
  status?: string;
  supportsReferences?: boolean;
  supportsEditing?: boolean;
  executable?: boolean;
};

/** Raw row from GET /api/hosted-providers/discovered-models. */
export type ApiGeneratorRow = {
  id?: string;
  label?: string;
  displayName?: string;
  provider?: string;
  providerId?: string;
  executable?: boolean;
};

/**
 * Map a Local Generator roster row to a selector option, FAILING CLOSED
 * (CDX-081): a missing `executable` or `status` field is treated as
 * unverified/disabled - never as available, and never defaulted to "Certified".
 * Only the backend asserting `executable: true` makes the option executable.
 */
export function toLocalGeneratorOption(row: LocalGeneratorRow): GeneratorOption {
  return {
    id: row.id,
    label: row.label,
    family: row.id,
    providerKind: "local",
    executable: row.executable === true,
    status: row.status || "Unknown",
    supportsReferences: !!row.supportsReferences,
    supportsEditing: !!row.supportsEditing,
  };
}

/**
 * Map a hosted discovered-model row to a selector option. Availability is only
 * asserted when the backend row says `executable: true` (CDX-081); otherwise the
 * option is disabled. `availability` (credit-label fallback) is "Connected" only
 * when the backend asserts executability - never invented from absence.
 */
export function toApiGeneratorOption(row: ApiGeneratorRow, falBalance: number | null): GeneratorOption {
  const providerId = (row.providerId || row.provider || "").toLowerCase();
  const credits = providerId === "fal" ? falBalance : null;
  const executable = row.executable === true;
  return {
    id: row.id || providerId + ":" + (row.label || row.displayName || "model"),
    label: row.label || row.displayName || row.id || "API model",
    providerKind: "cloud",
    providerId: providerId || undefined,
    modelId: row.id,
    executable,
    credits,
    availability: credits == null ? (executable ? "Connected" : "Balance unavailable") : undefined,
  };
}

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
