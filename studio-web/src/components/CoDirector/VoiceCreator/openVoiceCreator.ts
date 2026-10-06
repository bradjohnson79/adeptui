import type { VoiceIdentityMethod } from "../../voiceStudio/voiceIdentityRoute";

export const VOICE_CREATOR_HANDOFF_KEY = "adept_voice_creator_character";
export const OPEN_VOICE_CREATOR_EVENT = "adept:open-voice-creator";
export const VOICE_CREATOR_OPENED_EVENT = "adept:voice-creator-opened";

export type VoiceCreatorHandoff = {
  characterId?: string;
  method?: VoiceIdentityMethod | "";
};

export function readVoiceCreatorHandoff(): VoiceCreatorHandoff | null {
  try {
    const raw = sessionStorage.getItem(VOICE_CREATOR_HANDOFF_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as VoiceCreatorHandoff;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function writeVoiceCreatorHandoff(detail: VoiceCreatorHandoff): void {
  try {
    sessionStorage.setItem(VOICE_CREATOR_HANDOFF_KEY, JSON.stringify(detail));
  } catch {
    /* ignore */
  }
}

export function openVoiceCreator(detail: VoiceCreatorHandoff = {}): void {
  writeVoiceCreatorHandoff(detail);
  window.dispatchEvent(new CustomEvent(OPEN_VOICE_CREATOR_EVENT, { detail }));
}
