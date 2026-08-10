import type { StatusKind } from "./kinds";

export function mapComfyHealth(reachable: boolean, missingRequired = false): StatusKind {
  if (!reachable) return "Offline";
  return missingRequired ? "NeedsAttention" : "Ready";
}

export function mapProviderReachable(reachable: boolean): StatusKind {
  return reachable ? "Connected" : "Offline";
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
  return reachable ? "Provider Connected" : "Provider Offline";
}

export function gpuHealthLabel(ok: boolean): string {
  return ok ? "GPU Detected" : "GPU Unavailable";
}
