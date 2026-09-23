/**
 * Named Production menu availability — resolved outside the declarative catalog.
 * Each key maps to a concrete dependency; never blanket one signal onto unrelated tools.
 */
import type { Health } from "../types";

export type ProductAvailabilityStatus =
  | "Available"
  | "Requires setup"
  | "Provider unavailable"
  | "Local runtime offline"
  | "Draft"
  | "Blocked"
  | "Deferred";

export type ProductAvailability = {
  status: ProductAvailabilityStatus;
  /** Creator-facing dependency explanation for the badge */
  reason?: string;
};

export type ProductionAvailabilityKey =
  | "textToVideo"
  | "imageGeneration"
  | "oneFrame"
  | "threeFrame"
  | "timeline"
  | "audioStudio";

export type ProductionAvailability = Record<ProductionAvailabilityKey, ProductAvailability>;

const AVAILABLE: ProductAvailability = { status: "Available" };

function comfyOffline(health: Health | null, healthError: unknown): ProductAvailability | null {
  if (healthError) {
    return { status: "Local runtime offline", reason: "Studio API unreachable" };
  }
  if (!health) {
    return { status: "Requires setup", reason: "Checking local runtime…" };
  }
  if (health.comfy_probed === false) {
    return { status: "Requires setup", reason: "Checking local runtime…" };
  }
  if (!health.comfy_reachable) {
    return {
      status: "Local runtime offline",
      reason: "ComfyUI is offline — start ComfyUI for local generation",
    };
  }
  // Use REQUIRED-missing count, not the total. A missing optional/generator-specific
  // component (e.g. LTX 2.5 text encoder) must not block ALL generation — only the
  // affected generator. Other generators remain available. The previous logic used
  // the total missing count, which over-blocked when an optional component was missing.
  // If the required-missing list is present (including []), use ONLY that length.
  // [].length is 0 / falsy, so || would leak into all-missing IDs (optional
  // krea2_models, etc.) and wrongly block every generation tool.
  const requiredMissingIds = health.comfy?.missingRequiredModelComponentIds;
  const missingRequired = Array.isArray(requiredMissingIds)
    ? requiredMissingIds.length
    : (health.missing_model_component_ids?.length
      || health.missing_models?.length
      || 0);
  const missingOptional =
    (health.comfy?.missingModelComponentIds?.length || health.missing_model_component_ids?.length || health.missing_models?.length || 0)
    - missingRequired;
  if (missingRequired > 0) {
    return {
      status: "Requires setup",
      reason: "Required generation models are missing — open Source Manager",
    };
  }
  if (missingOptional > 0) {
    // Runtime is online and all REQUIRED models are present, but some optional/
    // generator-specific components are incomplete. Generation remains Available;
    // the affected generator's preflight will block only that generator.
    return null;
  }
  return null;
}

/** Comfy process reachable — excludes generator-specific required-model gaps. */
function comfyRuntimeGate(health: Health | null, healthError: unknown): ProductAvailability | null {
  if (healthError) {
    return { status: "Local runtime offline", reason: "Studio API unreachable" };
  }
  if (!health) {
    return { status: "Requires setup", reason: "Checking local runtime…" };
  }
  if (health.comfy_probed === false) {
    return { status: "Requires setup", reason: "Checking local runtime…" };
  }
  if (!health.comfy_reachable) {
    return {
      status: "Local runtime offline",
      reason: "ComfyUI is offline — start ComfyUI for local generation",
    };
  }
  return null;
}

function audioAvailability(health: Health | null, healthError: unknown): ProductAvailability {
  if (healthError) {
    return { status: "Local runtime offline", reason: "Studio API unreachable" };
  }
  if (!health) {
    return { status: "Requires setup", reason: "Checking audio providers…" };
  }
  const audioOk = health.operator?.audioProductionEnabled;
  if (audioOk === false) {
    return {
      status: "Requires setup",
      reason: "Requires audio provider setup",
    };
  }
  return AVAILABLE;
}

/**
 * Resolve per-tool availability from health/operator signals.
 * Image and video tools that need Comfy share that dependency; timeline/audio do not.
 */
export function resolveProductionAvailability(
  health: Health | null,
  healthError: unknown = null,
): ProductionAvailability {
  const comfyRuntime = comfyRuntimeGate(health, healthError);
  const comfyWithRequiredModels = comfyOffline(health, healthError);
  const videoOrAvailable = comfyWithRequiredModels || AVAILABLE;
  // Image Gen must not be blanketed by missing video checkpoints (e.g. a purged LTX 2.5).
  // Image families gate via their own preflight / Source Manager components.
  const imageOrAvailable = comfyRuntime || AVAILABLE;

  return {
    // Local video paths that enqueue through Comfy — still honor required-model gaps
    textToVideo: videoOrAvailable,
    imageGeneration: imageOrAvailable,
    oneFrame: videoOrAvailable,
    threeFrame: videoOrAvailable,
    // Timeline planning UI is available without Comfy; generation steps gate later
    timeline: healthError
      ? { status: "Local runtime offline", reason: "Studio API unreachable" }
      : AVAILABLE,
    audioStudio: audioAvailability(health, healthError),
  };
}

export function defaultProductionAvailability(): ProductionAvailability {
  return resolveProductionAvailability(null, null);
}
