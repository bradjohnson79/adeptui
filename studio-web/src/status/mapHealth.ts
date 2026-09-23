import type { StatusKind } from "./kinds";

export function mapComfyHealth(reachable: boolean, missingRequired = false): StatusKind {
  if (!reachable) return "Offline";
  return missingRequired ? "NeedsAttention" : "Ready";
}

export type ProviderProbe = {
  status?: string | null;
  reachable?: boolean | null;
  probed?: boolean | null;
};

export function isProviderProbeSkipped(probe?: ProviderProbe | null): boolean {
  if (!probe) return true;
  const status = String(probe.status || "").toLowerCase();
  return status === "skipped" || status === "not_probed" || probe.probed === false;
}

export function mapProviderReachable(reachable: boolean): StatusKind {
  return reachable ? "Connected" : "Offline";
}

export function mapProviderStatus(
  probe?: ProviderProbe | null,
  capabilityReady?: boolean | null,
): StatusKind {
  if (capabilityReady === true) return "Connected";
  if (capabilityReady === false) return "Offline";
  if (isProviderProbeSkipped(probe)) return "Checking";
  return probe?.reachable ? "Connected" : "Offline";
}

export function mapApiOk(ok: boolean): StatusKind {
  return ok ? "Online" : "Unavailable";
}

export function mapGpuOk(ok: boolean): StatusKind {
  return ok ? "Connected" : "NeedsAttention";
}

export function apiHealthLabel(ok: boolean, degraded = false): string {
  if (!ok) return "Studio API Unavailable";
  return degraded ? "Studio API Degraded" : "Studio API Online";
}

export function providerHealthLabel(reachable: boolean): string {
  return reachable ? "Providers Ready" : "Required Provider Unavailable";
}

export function providerStatusLabel(
  probe?: ProviderProbe | null,
  capabilityReady?: boolean | null,
): string {
  if (capabilityReady === true) return "Providers Ready";
  if (capabilityReady === false) return "Required Provider Unavailable";
  if (isProviderProbeSkipped(probe)) return "Providers…";
  return providerHealthLabel(Boolean(probe?.reachable));
}

export function gpuHealthLabel(ok: boolean): string {
  return ok ? "GPU Detected" : "GPU Unavailable";
}
