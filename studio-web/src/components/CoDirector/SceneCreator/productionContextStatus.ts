export type ProductionContextStatus = "idle" | "loading" | "loaded" | "failed";

export type ProductionContextPayload = {
  loaded?: boolean;
  handoffId?: string;
  revision?: number;
  fingerprint?: string;
  sceneId?: string;
  spatialMapId?: string;
  ersPackageId?: string;
  ersLibraryAssetId?: string;
  aspectRatio?: string;
};

export function deriveProductionContextStatus(args: {
  selectedProfileId?: string | null;
  requestedProfileId?: string | null;
  fetchInFlight: boolean;
  productionContext?: ProductionContextPayload | null;
}): ProductionContextStatus {
  const selected = String(args.selectedProfileId || "").trim();
  const requested = String(args.requestedProfileId || "").trim();
  const profile = requested || selected;
  if (!profile) return "idle";
  if (args.fetchInFlight) return "loading";
  const loaded = args.productionContext?.loaded === true;
  const matches =
    !requested ||
    String(args.productionContext?.handoffId || selected).trim() === requested;
  if (loaded && matches && selected) return "loaded";
  return "failed";
}
