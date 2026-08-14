/**
 * Prop Creator generate request + gate helpers.
 * User Control Law: unchecked source = zero jobs to that source.
 * New payload: generatorSources local[] / api[] / styleEngine.
 * Old scalars stay as fallback (candidate_count = sum of checked batches).
 */
import {
  DEFAULT_GENERATOR_PLAN,
  buildPropGeneratorSourcesPayload,
  fallbackGenerateScalars,
  hydrateGeneratorPlan,
  planHasExecutableWork,
  propProvenanceLabel,
  summarizeCandidatePlan,
  type CharacterGeneratorPlan,
  type GeneratorSourcesPayload,
} from "../../generators/generatorPlan";

export type PropGeneratorPlan = CharacterGeneratorPlan;

export function sourcesFromPropGenerator(generator?: unknown): CharacterGeneratorPlan {
  return hydrateGeneratorPlan(generator);
}

export function defaultPropGeneratorPlan(): CharacterGeneratorPlan {
  return { ...DEFAULT_GENERATOR_PLAN };
}

export function propGenerateRequest(plan: CharacterGeneratorPlan) {
  const generatorSources = buildPropGeneratorSourcesPayload(plan);
  const scalars = fallbackGenerateScalars(plan);
  return {
    generatorSources,
    local_enabled: scalars.local_enabled,
    api_enabled: scalars.api_enabled,
    local_family: scalars.local_family,
    api_model: scalars.api_model,
    candidate_count: scalars.candidate_count,
  };
}

export function persistGeneratorPayload(plan: CharacterGeneratorPlan) {
  const generatorSources = buildPropGeneratorSourcesPayload(plan);
  const scalars = fallbackGenerateScalars(plan);
  return {
    local: generatorSources.local,
    api: generatorSources.api,
    styleEngine: generatorSources.styleEngine,
    stage2Enabled: generatorSources.stage2Enabled,
    stage2Family: generatorSources.stage2Family,
    local_enabled: plan.localEnabled,
    api_enabled: plan.apiEnabled,
    local_family: scalars.local_family,
    api_model: scalars.api_model,
  };
}

export function plannedCandidateCount(plan: CharacterGeneratorPlan): number {
  return summarizeCandidatePlan(plan).totalImages;
}

export function propGenerateBlockReason(opts: {
  name: string;
  plan: CharacterGeneratorPlan;
  busy?: boolean;
}): string | null {
  if (!opts.name.trim()) return "Name the Prop to generate images.";
  if (!planHasExecutableWork(opts.plan)) {
    return "Enable a Local or Cloud generator to create prop images.";
  }
  if (opts.busy) return "Generation already in progress.";
  return null;
}

export function candidateStatusLabel(status: string): "Generating" | "Complete" | "Failed" | "Retry" {
  if (status === "complete") return "Complete";
  if (status === "failed") return "Failed";
  return "Generating";
}

export { propProvenanceLabel };
export type { GeneratorSourcesPayload };
