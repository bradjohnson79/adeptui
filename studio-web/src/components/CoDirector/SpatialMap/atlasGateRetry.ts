/** Gate-retry context for Atlas generate. Production Express retries stay on GPT Image 2. */

export type AtlasGateRetryInput = {
  engineNote?: string;
  generationMethod?: string;
  environmentType?: string;
  metaSource?: string;
  origRefs: string[];
  description: string;
  retryReason: string;
  retries: number;
  atlasLook: unknown;
  clickId: string;
  variant?: string;
  reuseGuideAssetId?: string;
};

export type AtlasGateRetryRequest = {
  attachmentAssetIds: string[];
  prompt: string;
  context: Record<string, unknown>;
};

export function buildAtlasGateRetryRequest(input: AtlasGateRetryInput): AtlasGateRetryRequest {
  const designedRetry = input.metaSource === "designed" || input.variant === "express" || !input.origRefs[0];
  const design = designedRetry;
  const route = design
    ? input.origRefs[0]
      ? "designed_with_reference"
      : "designed"
    : "reconstruct";
  const attachmentAssetIds = input.origRefs[0] ? [input.origRefs[0]] : [];
  return {
    attachmentAssetIds,
    prompt: input.description || "Create a roofless top-down Atlas Shot of this location.",
    context: {
      mode: input.variant,
      scene_description: input.description,
      generation_route: route,
      generationRoute: route,
      require_source: !design,
      ...(designedRetry
        ? {
            generationMethod: "api",
            generation_method: "api",
            hostedModelId: "gpt-image-2-kie",
            hosted_model_id: "gpt-image-2-kie",
            source: "api",
          }
        : { attachment_asset_ids: attachmentAssetIds }),
      retry_reason: input.retryReason,
      reconstruction_retry: input.retries + 1,
      atlasLook: input.atlasLook,
      atlas_look: input.atlasLook,
      atlasPerfClickId: input.clickId,
      atlas_perf_click_id: input.clickId,
    },
  };
}
