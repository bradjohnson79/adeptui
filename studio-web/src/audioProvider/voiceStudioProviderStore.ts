import {
  VOICE_STUDIO_PROVIDER_EVENT,
  VOICE_STUDIO_PROVIDER_KEY,
  normalizeProviderSource,
  type AdeptAudioProviderSource,
} from "./types";

const VOICE_ID_KEY = "adept.voiceStudio.elevenlabsVoiceId";
const MODEL_ID_KEY = "adept.voiceStudio.elevenlabsModelId";
const listeners = new Set<(value: AdeptAudioProviderSource) => void>();

function emit(value: AdeptAudioProviderSource) {
  listeners.forEach((fn) => {
    try { fn(value); } catch { /* ignore */ }
  });
  try {
    window.dispatchEvent(new CustomEvent(VOICE_STUDIO_PROVIDER_EVENT, { detail: value }));
  } catch { /* ignore */ }
}

function readStored(): AdeptAudioProviderSource {
  try {
    return normalizeProviderSource(localStorage.getItem(VOICE_STUDIO_PROVIDER_KEY));
  } catch {
    return "local";
  }
}

export function getVoiceStudioProvider(): AdeptAudioProviderSource {
  return readStored();
}

export function setVoiceStudioProvider(next: AdeptAudioProviderSource) {
  const value = next === "elevenlabs" ? "elevenlabs" : "local";
  try { localStorage.setItem(VOICE_STUDIO_PROVIDER_KEY, value); } catch { /* ignore */ }
  emit(value);
}

export function getElevenLabsVoiceId(): string {
  try { return String(localStorage.getItem(VOICE_ID_KEY) || ""); } catch { return ""; }
}

export function setElevenLabsVoiceId(voiceId: string) {
  try { localStorage.setItem(VOICE_ID_KEY, String(voiceId || "")); } catch { /* ignore */ }
}

export function getElevenLabsModelId(): string {
  try { return String(localStorage.getItem(MODEL_ID_KEY) || ""); } catch { return ""; }
}

export function setElevenLabsModelId(modelId: string) {
  try { localStorage.setItem(MODEL_ID_KEY, String(modelId || "")); } catch { /* ignore */ }
}

export function subscribeVoiceStudioProvider(fn: (value: AdeptAudioProviderSource) => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
