import {
  AUDIO_STUDIO_PROVIDER_EVENT,
  AUDIO_STUDIO_PROVIDER_KEY,
  normalizeProviderSource,
  type AdeptAudioProviderSource,
} from "./types";

function readStored(): AdeptAudioProviderSource {
  try {
    return normalizeProviderSource(localStorage.getItem(AUDIO_STUDIO_PROVIDER_KEY));
  } catch {
    return "local";
  }
}

let current: AdeptAudioProviderSource = typeof localStorage === "undefined" ? "local" : readStored();
const listeners = new Set<(value: AdeptAudioProviderSource) => void>();

function emit(value: AdeptAudioProviderSource) {
  listeners.forEach((fn) => {
    try { fn(value); } catch { /* ignore */ }
  });
  try {
    window.dispatchEvent(new CustomEvent(AUDIO_STUDIO_PROVIDER_EVENT, { detail: value }));
  } catch { /* ignore */ }
}

export function getAudioStudioProvider(): AdeptAudioProviderSource {
  return current;
}

export function setAudioStudioProvider(next: AdeptAudioProviderSource) {
  const value = normalizeProviderSource(next);
  if (value === current) return;
  current = value;
  try { localStorage.setItem(AUDIO_STUDIO_PROVIDER_KEY, value); } catch { /* ignore */ }
  emit(value);
}

export function subscribeAudioStudioProvider(fn: (value: AdeptAudioProviderSource) => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** Cross-tab / cross-module sync */
export function bindAudioStudioProviderStorage() {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => {
    if (e.key !== AUDIO_STUDIO_PROVIDER_KEY) return;
    const value = normalizeProviderSource(e.newValue);
    if (value === current) return;
    current = value;
    emit(value);
  };
  window.addEventListener("storage", onStorage);
  return () => window.removeEventListener("storage", onStorage);
}
