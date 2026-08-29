import type {
  ApiModelsSectionMeta,
  DiscoveredApiModel,
  Modality,
  ModalityModelSections,
  ModelDescriptor,
} from "./contracts";

/** Capability-field isolation. Never filter by label or name. */
export function modelsForModality<T extends { modality?: string | null }>(
  models: readonly T[] | null | undefined,
  modality: Modality,
): T[] {
  if (!Array.isArray(models) || models.length === 0) return [];
  return models.filter((model) => model.modality === modality);
}

export type ProductionControlModelsPayload = {
  models?: ModelDescriptor[];
  sections?: {
    local?: ModelDescriptor[];
    api?: DiscoveredApiModel[];
  };
  api?: ApiModelsSectionMeta;
};

/**
 * Canonical post-process for GET /api/production-control/models?modality=.
 * Local/API slices are taken from that payload, then re-checked so a
 * cached or swapped response cannot leak another modality into the menu.
 */
export function sectionsFromProductionControlModels(
  payload: ProductionControlModelsPayload | unknown,
  modality: Modality,
): ModalityModelSections {
  const list =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as ProductionControlModelsPayload)
      : { models: Array.isArray(payload) ? (payload as ModelDescriptor[]) : [] };

  const rawLocal =
    list.sections?.local ??
    (Array.isArray(list.models) ? list.models.filter((m) => m.locality === "local") : []);
  const rawApi =
    list.sections?.api ??
    (Array.isArray(list.models) ? list.models.filter((m) => m.locality === "hosted") : []);

  return {
    local: modelsForModality(rawLocal, modality),
    api: modelsForModality(rawApi, modality),
    apiMeta: list.api,
  };
}
