/** Shape guard for GET /api/diagnostics/run. Error/504 bodies must not be treated as results. */
export function isDiagnosticsResult(data: unknown): data is {
  classification: { faultDomain: string; confidence?: string; evidence?: string };
  layers: Record<string, unknown>;
  totalMs?: number;
} {
  if (!data || typeof data !== "object") return false;
  const rec = data as Record<string, unknown>;
  const classification = rec.classification;
  if (!classification || typeof classification !== "object") return false;
  const faultDomain = (classification as Record<string, unknown>).faultDomain;
  if (typeof faultDomain !== "string" || faultDomain.length === 0) return false;
  const layers = rec.layers;
  return !!layers && typeof layers === "object";
}

/** Optional-chain reader so missing classification never throws. */
export function readFaultDomain(data: unknown): string | undefined {
  if (!data || typeof data !== "object") return undefined;
  const classification = (data as { classification?: { faultDomain?: unknown } }).classification;
  return typeof classification?.faultDomain === "string" ? classification.faultDomain : undefined;
}