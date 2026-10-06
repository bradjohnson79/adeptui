/** ORDER 15 — Local | ElevenLabs (API) provider source */
export type AdeptAudioProviderSource = "local" | "elevenlabs";

export type ElevenLabsHealth = {
  configured: boolean;
  connectionStatus: string;
  message: string;
  displayName: string;
};

export const AUDIO_STUDIO_PROVIDER_EVENT = "adept:audio-studio-provider";
export const VOICE_STUDIO_PROVIDER_EVENT = "adept:voice-studio-provider";

export const AUDIO_STUDIO_PROVIDER_KEY = "adept.audioStudio.providerSource";
export const VOICE_STUDIO_PROVIDER_KEY = "adept.voiceStudio.providerSource";

export function normalizeProviderSource(value: unknown): AdeptAudioProviderSource {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === "elevenlabs" || raw === "eleven" || raw === "api" || raw === "eleven_labs") return "elevenlabs";
  return "local";
}
