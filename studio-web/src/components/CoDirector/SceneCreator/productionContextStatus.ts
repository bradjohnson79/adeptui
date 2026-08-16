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

export type IntegrityCaption =
  | { kind: "hidden" }
  | { kind: "verified" }
  | { kind: "advisory"; count: number }
  | { kind: "blocked" }
  | { kind: "connections"; llmUnavailable: boolean };

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

export function deriveIntegrityCaption(args: {
  cdStatus: ProductionContextStatus;
  readiness?: {
    status?: string;
    issues?: { type?: string }[];
    llm?: { available?: boolean } | null;
  } | null;
}): IntegrityCaption {
  if (args.cdStatus === "idle") return { kind: "hidden" };
  if (args.cdStatus !== "loaded") return { kind: "hidden" };
  const status = String(args.readiness?.status || "").trim();
  if (status === "blocked") return { kind: "blocked" };
  if (status === "advisory") {
    const count = (args.readiness?.issues || []).filter((i) => i.type === "advisory").length || 1;
    return { kind: "advisory", count };
  }
  if (status === "llm_unavailable") return { kind: "connections", llmUnavailable: true };
  if (status === "pass") return { kind: "verified" };
  return { kind: "hidden" };
}

export function tickMark(state: string | undefined): string {
  if (state === "ok") return "✓";
  if (state === "warn") return "⚠";
  if (state === "fail") return "✕";
  return "·";
}
