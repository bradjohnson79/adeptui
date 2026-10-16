export type ComfyPlatform = "windows" | "mac" | "linux" | "other";

/** Official ComfyUI terminal install. The user pastes this; Adept does not run it. */
export function comfyInstallCommand(platform: ComfyPlatform): string {
  if (platform === "windows") return "pip install comfy-cli; comfy install";
  return "pip install comfy-cli && comfy install";
}

/**
 * ComfyUI is offered only for a local profile that still needs it.
 * API Install never asks for ComfyUI. Hybrid asks only when a local model was chosen.
 */
export function comfyInstallRequired(
  profile: "local" | "hybrid" | "api",
  selectedLocalIds: string[],
  comfyReady: boolean,
): boolean {
  if (comfyReady || profile === "api") return false;
  if (profile === "local") return true;
  return selectedLocalIds.length > 0;
}
