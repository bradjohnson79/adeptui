/** Compact dock chip labels so Local/API and modalities fit one row. */
export function truncateDockLabel(value: string, maxChars = 14): string {
  const text = (value || "").trim();
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`;
}

export type AdeptAudioProviderSourceLike = "local" | "elevenlabs" | string | null | undefined;

/**
 * ORDER20 NO-GO REPAIR — Audio footer pill binds to audioStudioProvider only.
 * Never model names (ACE-Step / MMAudio / Gemma). Chrome is Local | API — ElevenLabs.
 */
export function formatAudioStudioProviderPill(
  source: AdeptAudioProviderSourceLike,
  displayName?: string | null,
): string {
  const raw = String(source || "").trim().toLowerCase();
  if (raw === "elevenlabs" || raw === "eleven" || raw === "api" || raw === "eleven_labs") {
    const name = (displayName || "").trim();
    // Prefer Systems displayName when it already names ElevenLabs; otherwise canonical chrome.
    if (name && /eleven/i.test(name) && name.length <= 22) return name;
    return "ElevenLabs API";
  }
  return "Local";
}

type AudioLabelSource = {
  id?: string | null;
  label?: string | null;
  locality?: string | null;
  providerId?: string | null;
} | null | undefined;

/** Drawer row label for hosted audio rows (not used for footer pill). */
export function formatAudioMenuRowLabel(model: AudioLabelSource): string {
  if (!model) return "ElevenLabs API";
  if (model.locality === "local") return "Local";
  const provider = `${model.providerId || ""}`.toLowerCase();
  if (provider === "elevenlabs") return "ElevenLabs API";
  return "Audio";
}

/**
 * Legacy helper — ORDER20 NO-GO: must not surface ACE-Step on the footer pill.
 * Always collapses to Local | API — ElevenLabs.
 */
export function formatAudioDockPillLabel(
  model: AudioLabelSource,
  _fallbackLabel?: string | null,
): string {
  const id = `${model?.id || ""}`.toLowerCase();
  const label = `${model?.label || ""}`.toLowerCase();
  if (id.includes("eleven") || label.includes("eleven")) return "ElevenLabs API";
  return "Local";
}
