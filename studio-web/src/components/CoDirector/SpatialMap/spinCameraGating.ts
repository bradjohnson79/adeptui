/**
 * Pure gating logic for the Spin Camera "Create Spin Images" action.
 *
 * Mirrors the contract: disabled until spin camera exists + placement is
 * centered + provider selected + provider executable + map has a background atlas.
 */
import type { SpinCameraPlacement } from "./types";

export type SpinProviderOption = {
  id: string;
  label: string;
  executable: boolean;
  supportsReferences?: boolean;
};

export function createSpinImagesDisabledReason(
  spinCamera: SpinCameraPlacement | null | undefined,
  centerStatus: { centered: boolean } | null | undefined,
  providerId: string,
  providerOptions: ReadonlyArray<SpinProviderOption>,
  hasBackgroundAssetId: boolean,
): string | null {
  if (!hasBackgroundAssetId) {
    return "Create or assign an Atlas Shot before generating spin views.";
  }
  if (!spinCamera) {
    return "Place the Spin Camera on the map first.";
  }
  if (!centerStatus?.centered) {
    return "Move the Spin Camera closer to the scene center.";
  }
  if (!providerId) {
    return "Choose a cloud image generator.";
  }
  const provider = providerOptions.find((o) => o.id === providerId);
  if (!provider) {
    return "Choose a cloud image generator.";
  }
  if (!provider.executable) {
    return `${provider.label} is not available right now.`;
  }
  return null;
}

export function spinViewIsPending(status: string): boolean {
  const s = String(status || "").toLowerCase();
  return s === "queued" || s === "generating";
}

export function spinViewIsFailed(status: string): boolean {
  const s = String(status || "").toLowerCase();
  return s === "failed" || s === "error" || s === "canceled" || s === "cancelled";
}
