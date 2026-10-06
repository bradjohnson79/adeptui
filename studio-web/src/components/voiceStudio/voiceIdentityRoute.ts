export type VoiceIdentityMethod = "create" | "existing" | "clone" | "elevenlabs";

export type VoiceIdentityAction = "design" | "clone" | "none";

export function voiceIdentityAction(method: VoiceIdentityMethod | null): VoiceIdentityAction {
  if (method === "create") return "design";
  if (method === "clone") return "clone";
  return "none";
}
